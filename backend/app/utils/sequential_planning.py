"""
Sequential Planning을 이용한 보고서 계획 생성 모듈

Template의 prompt_system을 활용하여 Claude Sequential Planning MCP를 사용하고
보고서의 구조화된 계획을 생성합니다.
"""

import json
import logging
import time
from typing import Dict, Optional, Any, List

from app.utils.claude_client import ClaudeClient
from app.utils.prompts import get_base_plan_prompt, get_advanced_planner_prompt, get_base_report_prompt, get_for_plan_source_type_basic_prompt_system, get_for_plan_source_type_basic_prompt_user

logger = logging.getLogger(__name__)

PROMPT_OPTIMIZATION_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


class SequentialPlanningError(Exception):
    """Sequential Planning 실행 중 발생하는 예외"""
    pass


class TimeoutError(SequentialPlanningError):
    """Sequential Planning 응답시간 초과"""
    pass


async def sequential_planning(
    topic: str,
    template_id: Optional[int] = None,
    user_id: Optional[str] = None,
    is_web_search: bool = False,
    is_template_used: bool = True,
    topic_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Sequential Planning을 이용한 보고서 계획 수립

    Template의 prompt_system을 가이드로 사용하여 보고서의 구조화된 계획을 생성합니다.

    Args:
        topic: 보고서 주제 (필수)
        template_id: 사용할 템플릿 ID (선택, None이면 default 사용)
        user_id: 사용자 ID (template_id 지정 시 권한 확인용)
        is_web_search: Claude 웹 검색 도구 활성화 여부
        is_template_used: If True, use template-based prompt (get_base_plan_prompt).
                          If False, use advanced planner prompt (get_advanced_planner_prompt).
                          Default: True
        topic_id: Topic이 생성된 경우 topic_id 전달. isTemplateUsed=false일 때 프롬프트 최적화 저장용

    Returns:
        {
            "plan": "# 보고서 계획\n## 개요\n...",
            "sections": [
                {
                    "title": "개요",
                    "description": "보고서의 전체 개요",
                    "order": 1
                },
                ...
            ],
            "prompt_user": "## 선택된 역할: ...\n..." (only when is_template_used=False),
            "prompt_system": "## BACKGROUND\n..." (only when is_template_used=False)
        }

    Raises:
        SequentialPlanningError: 보고서 계획 생성 실패
        TimeoutError: 응답시간 초과 (> 2초)
        ValueError: 필수 파라미터 누락

    """

    # 1. 입력 검증
    if not topic or not isinstance(topic, str):
        raise ValueError("topic is required and must be a string")

    if len(topic) > 200:
        raise ValueError("topic must be less than 200 characters")

    logger.info(f"Sequential Planning started - topic={topic}, template_id={template_id}")

    try:
        if is_template_used:
            return await _single_step_planning(topic, is_web_search)
        return await _two_step_planning(topic, user_id, is_web_search, topic_id)

    except Exception as e:
        logger.error(f"Sequential Planning failed - error={str(e)}", exc_info=True)
        raise SequentialPlanningError(f"Failed to generate plan: {str(e)}")


async def _single_step_planning(topic: str, is_web_search: bool) -> Dict[str, Any]:
    """Template 기반 프롬프트를 활용한 단일 단계 계획 생성"""
    start_time = time.time()

    guidance_prompt = get_base_plan_prompt()
    input_prompt = f"""요청 주제: {topic} {guidance_prompt} """

    plan_response = await _call_sequential_planning(
        input_prompt,
        is_web_search=is_web_search
    )

    plan_dict = _parse_plan_response(plan_response)

    elapsed = time.time() - start_time
    logger.info(
        "Sequential Planning (single-step) completed - elapsed=%0.2fs, sections=%d",
        elapsed,
        len(plan_dict["sections"])
    )

    return plan_dict


async def _two_step_planning(
    topic: str,
    user_id: Optional[str],
    is_web_search: bool,
    topic_id: Optional[int]
) -> Dict[str, Any]:
    """Advanced Role Planner 기반 2단계 계획 생성 및 DB 저장"""
    start_time = time.time()

    logger.info("Sequential Planning (two-step) started - using Advanced Role Planner")

    # 1단계: Advanced Role Planner 호출
    advanced_prompt = get_advanced_planner_prompt().replace("{{USER_TOPIC}}", topic)
    first_response = await _call_sequential_planning(
        advanced_prompt,
        is_web_search=is_web_search
    )

    logger.info("Sequential Planning - first API call completed")

    first_response_json = json.loads(_extract_json_from_response(first_response))
    logger.info(
        "Sequential Planning - first response parsed (keys=%s)",
        list(first_response_json.keys())
    )

    # Advanced Role Planner 응답에서 필드 추출
    prompt_fields = _extract_prompt_fields(first_response_json)

    # 최적화된 프롬프트 구성
    optimized_prompt_system = _build_prompt_system_from_fields(
        role=prompt_fields["role"],
        context=prompt_fields["context"],
        output_format=prompt_fields["output_format"], 
    )
    
    optimized_prompt_user = _build_optimized_prompt(
        prompt_user=optimized_prompt_system,
        task=prompt_fields["task"]
    )
    
    input_prompt_system = get_for_plan_source_type_basic_prompt_system()
    input_prompt_user = get_for_plan_source_type_basic_prompt_user().replace("{{OPTIMIZED_PROMPT_JSON}}", optimized_prompt_user)

    # 2단계: 최적화된 프롬프트로 계획 생성
    second_response = await _call_sequential_planning(
        input_prompt_user,
        is_web_search=is_web_search,
        system_prompt=input_prompt_system
    )

    logger.info("Sequential Planning - second API call completed")

    plan_dict = _parse_plan_response(second_response)
    plan_dict["prompt_user"] = input_prompt_user
    plan_dict["prompt_system"] = input_prompt_system


    if topic_id is not None:
        try:
            from app.database.prompt_optimization_db import PromptOptimizationDB

            emotional_needs = prompt_fields.get("emotional_needs", {})

            logger.info(
                "Sequential Planning - Saving prompt optimization result - topic_id=%s",
                topic_id
            )

            PromptOptimizationDB.create(
                topic_id=topic_id,
                user_id=int(user_id) if isinstance(user_id, str) else user_id,
                user_prompt=optimized_prompt_system,
                hidden_intent=prompt_fields.get("hidden_intent"),
                emotional_needs=emotional_needs,
                underlying_purpose=prompt_fields.get("underlying_purpose"),
                formality=emotional_needs.get("formality"),
                confidence_level=emotional_needs.get("confidence_level"),
                decision_focus=emotional_needs.get("decision_focus"),
                output_format=prompt_fields.get("output_format"),
                original_topic=topic,
                role=prompt_fields.get("role"),
                context=prompt_fields.get("context"),
                task=prompt_fields.get("task"),
                model_name=PROMPT_OPTIMIZATION_DEFAULT_MODEL,
                latency_ms=int((time.time() - start_time) * 1000)
            )

            # ✅ NEW: output_format 미저장 시 경고
            if not prompt_fields.get("output_format"):
                logger.warning(
                    "Sequential Planning - output_format not detected in Claude response - topic_id=%s",
                    topic_id
                )

            logger.info(
                "Sequential Planning - Prompt optimization result saved - topic_id=%s",
                topic_id
            )
        except Exception as opt_exc:
            logger.warning(
                "Sequential Planning - Prompt optimization result save failed (non-blocking) - topic_id=%s, error=%s",
                topic_id,
                str(opt_exc),
                exc_info=True
            )

    elapsed = time.time() - start_time
    logger.info(
        "Sequential Planning (two-step) completed - elapsed=%0.2fs, sections=%d",
        elapsed,
        len(plan_dict["sections"])
    )

    return plan_dict

def _extract_json_from_response(response_text: str) -> str:
    """
    Claude 응답에서 JSON 추출
    마크다운 코드블록(```json ... ```)에 감싸져 있을 수 있음

    Args:
        response_text: Claude API 원본 응답

    Returns:
        정제된 JSON 문자열
    """
    text = response_text.strip()

    # 마크다운 코드블록 패턴: ```json ... ``` 또는 ``` ... ```
    if text.startswith("```"):
        # 시작 마크다운 제거
        lines = text.split("\n")

        # 첫 줄에서 ``` 제거 (```json 또는 ```)
        start_idx = 0
        if lines[0].startswith("```"):
            start_idx = 1

        # 마지막 줄에서 ``` 제거
        end_idx = len(lines)
        if lines[-1].strip() == "```":
            end_idx = len(lines) - 1

        text = "\n".join(lines[start_idx:end_idx]).strip()

    return text


async def _call_sequential_planning(
    user_prompt: str,
    is_web_search: bool = False,
    system_prompt: Optional[str] = None
) -> str:
    """
    Claude API를 호출하여 Sequential Planning 실행

    Args:
        user_prompt: 입력 받은 사용자 프롬프트
        is_web_search: Claude 웹 검색 활성화 여부
        system_prompt: Claude system prompt (없으면 기본값 사용)

    Returns:
        Claude API 응답 (JSON 문자열)

    Raises:
        SequentialPlanningError: API 호출 실패
    """
    try:
        logger.info(f"Calling Claude API for sequential planning - using fast model")
        system_prompt_text = system_prompt or "You are an expert in creating structured report plans. Respond only with valid JSON."

        # ClaudeClient 초기화 및 빠른 모델 사용
        claude = ClaudeClient()
        
        # 메시지 구성
        messages = [
            {
                "role": "user",
                "content": user_prompt
            }
        ]

        # 빠른 모델로 호출 (Haiku - 응답 속도 우선)
        plan_text, input_tokens, output_tokens = claude.chat_completion_fast(
            messages=messages,
            system_prompt=system_prompt_text,
            isWebSearch=is_web_search
        )

        logger.info(
            f"Claude API response received - "
            f"input_tokens={input_tokens}, "
            f"output_tokens={output_tokens}"
        )

        return plan_text

    except Exception as e:
        logger.error(f"Claude API call failed - error={str(e)}", exc_info=True)
        raise SequentialPlanningError(f"Claude API call failed: {str(e)}")

def _parse_plan_response(plan_text: str) -> Dict[str, Any]:
    """
    Claude 응답을 파싱하여 plan과 sections 추출

    Args:
        plan_text: Claude API 응답 텍스트 (JSON)

    Returns:
        {
            "plan": "마크다운 형식의 계획",
            "sections": [...]
        }

    Raises:
        SequentialPlanningError: JSON 파싱 실패
    """
    try:
        # 응답 텍스트 로깅 (디버깅용)
        logger.debug(f"Parsing plan response - length={len(plan_text)}, first_100_chars={plan_text[:100]}")

        # 응답 정제
        cleaned_text = _extract_json_from_response(plan_text)

        if not cleaned_text.strip():
            logger.error(f"Empty response after cleaning - original_length={len(plan_text)}")
            raise SequentialPlanningError("Received empty response from Claude API")

        # JSON 파싱 (후행 텍스트가 있어도 첫 번째 객체만 파싱)
        decoder = json.JSONDecoder()
        plan_json, end_idx = decoder.raw_decode(cleaned_text)
        trailing = cleaned_text[end_idx:].strip()
        if trailing:
            logger.debug("Trailing non-JSON content after plan payload ignored")

        # 새 아웃라인(JSON bullet) 형식 → 기존 sections 스키마로 정규화
        plan_json = _normalize_plan_json(plan_json)

        # Sections 추출
        sections = plan_json.get("sections", [])

        # 마크다운 형식의 plan 생성
        plan_md = _build_text_plan(plan_json)
        return {
            "plan": plan_md,
            "sections": sections
        }

    except Exception as e:
        logger.error(f"Failed to parse plan response - error={str(e)}", exc_info=True)
        raise SequentialPlanningError(f"Failed to parse plan response: {str(e)}")


OUTLINE_SECTION_ORDER = [
    "TITLE",
    "DATE",
    "BACKGROUND",
    "MAIN_CONTENT",
    "SUMMARY",
    "CONCLUSION",
]

SECTION_TITLE_LABELS = {
    "TITLE": "제목",
    "DATE": "날짜",
    "BACKGROUND": "배경",
    "MAIN_CONTENT": "주요 내용",
    "SUMMARY": "요약",
    "CONCLUSION": "결론",
}


def _normalize_plan_json(plan_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    두 번째 콜(Call#2)에서 반환되는 bullet 기반 아웃라인 JSON을
    기존 sections 스키마(title/description/key_points/order)로 변환한다.

    기존 sections 포맷이 이미 있으면 그대로 반환한다.
    """

    sections = plan_json.get("sections")
    if isinstance(sections, list) and sections:
        return plan_json

    has_outline_keys = any(key in plan_json for key in OUTLINE_SECTION_ORDER)
    if not has_outline_keys:
        return plan_json

    normalized_sections: List[Dict[str, Any]] = []
    normalized_title = plan_json.get("title")

    for key in OUTLINE_SECTION_ORDER:
        if key not in plan_json:
            continue

        bullets = _coerce_to_list(plan_json.get(key))
        if not bullets:
            continue

        if key == "TITLE" and not normalized_title:
            normalized_title = bullets[0]

        section_title = SECTION_TITLE_LABELS.get(key, key)
        description = bullets[0] if bullets else ""
        key_points = bullets[1:] if len(bullets) > 1 else []

        normalized_sections.append({
            "title": section_title,
            "description": description,
            "key_points": key_points,
            "order": len(normalized_sections) + 1
        })

    return {
        **plan_json,
        "title": normalized_title or "보고서 계획",
        "sections": normalized_sections,
        "estimated_word_count": plan_json.get("estimated_word_count", 0),
    }


def _coerce_to_list(raw_value: Any) -> List[str]:
    """단일 값/리스트를 문자열 리스트로 보정한다."""
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value if item is not None]
    if raw_value is None:
        return []
    return [str(raw_value)]


def _build_text_plan(plan_json: Dict[str, Any]) -> str:
    """
    JSON 계획을 plan text로 변환

    Args:
        plan_json: Claude 응답 JSON

    Returns:
        plan text 계획 텍스트
    """
    title = plan_json.get("title", "보고서 계획")
    sections = plan_json.get("sections", [])
    #TODO : 우선도 낮음, plan 시 estimated_word_count가 없음 임시 조치.
    #estimated_word_count = plan_json.get("estimated_word_count", 8000)
    estimated_word_count = "8000"

    lines = [
        f"{title}",
        "",
        f"예상 분량: {estimated_word_count}자",
        f"예상 섹션 수: {len(sections)}개",
        "",
    ]

    # 섹션별 계획 추가
    for section in sections:
        section_title = section.get("title", "무제")
        description = section.get("description", "")
        key_points = section.get("key_points", [])

        lines.append(f" {section_title}")
        lines.append("")

        if description:
            lines.append(f"설명: {description}")
            lines.append("")

        if key_points:
            lines.append("주요 포인트:")
            for point in key_points:
                lines.append(f"- {point}")
            lines.append("")

    return "\n".join(lines)

def _extract_prompt_fields(first_response_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Role/Context/Task 및 감정적 니즈 필드 추출 및 기본값 제공

    Args:
        first_response_json: Advanced Role Planner의 첫 번째 API 응답 JSON

    Returns:
        {
            "hidden_intent": str,
            "emotional_needs": {"formality": str, "confidence_level": str, "decision_focus": str},
            "underlying_purpose": str,
            "role": str,
            "context": str,
            "task": str
        }
    """
    restructured = first_response_json.get("restructured_prompt", {}) if isinstance(first_response_json.get("restructured_prompt", {}), dict) else {}
    analysis = first_response_json.get("analysis", {}) if isinstance(first_response_json.get("analysis", {}), dict) else {}

    # 감정적 니즈 추출 (emotional_needs dict에서 개별 필드 추출)
    emotional_needs_raw = first_response_json.get("emotional_needs", {})
    if not isinstance(emotional_needs_raw, dict):
        emotional_needs_raw = {}

    emotional_needs = {
        "formality": emotional_needs_raw.get("formality"),
        "confidence_level": emotional_needs_raw.get("confidence_level"),
        "decision_focus": emotional_needs_raw.get("decision_focus")
    }

    role = (
        restructured.get("role")
        or first_response_json.get("role")
        or first_response_json.get("selected_role")
        or "전문가"
    )
    context = (
        restructured.get("context")
        or first_response_json.get("context")
        or first_response_json.get("framework")
    )

    output_format_raw = first_response_json.get("output_format")
    if isinstance(output_format_raw, dict):
        output_format_lines = []
        for key, value in output_format_raw.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = str(value)
            output_format_lines.append(f"""{key}:\n{value_str}""")
        output_format = "\n".join(output_format_lines)
    elif output_format_raw is None:
        output_format = ""
    else:
        output_format = str(output_format_raw)

    task = (
        restructured.get("task")
        or first_response_json.get("task")
        or "주어진 주제를 기반으로 보고서 계획을 작성하세요."
    )

    hidden_intent = (
        first_response_json.get("hidden_intent")
        or ""
    )

    underlying_purpose = (
        first_response_json.get("underlying_purpose")
        or ""
    )

    return {
        "hidden_intent": hidden_intent,
        "emotional_needs": emotional_needs,
        "underlying_purpose": underlying_purpose,
        "role": role,
        "context": context,
        "output_format": output_format,
        "task": task
    }


def _build_prompt_system_from_fields(role: str, context: str, output_format: str) -> str:
    """
    role/context/output_format를 system prompt 상단에 반영하고 기본 마크다운 규칙을 이어붙인다.
    """
    role_text = role or "전문가"
    context_text = context or "맥락 정보가 제공되지 않았습니다."

    return f"""{role_text}

## 맥락 
{context_text}

> 모든 대답은 자연스러운 한국어로 작성되어야 합니다.
"""

def _build_optimized_prompt(prompt_user: str, task: str) -> str:
    """
    role/context/output_format를 system prompt 상단에 반영하고 기본 마크다운 규칙을 이어붙인다.
    """
    return f"""{prompt_user}
## TASK
{task}

"""
