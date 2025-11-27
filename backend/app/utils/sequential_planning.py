"""
Sequential Planning을 이용한 보고서 계획 생성 모듈

Template의 prompt_system을 활용하여 Claude Sequential Planning MCP를 사용하고
보고서의 구조화된 계획을 생성합니다.
"""

import json
import logging
import time
from typing import Dict, Optional, Any

from app.utils.claude_client import ClaudeClient
from app.utils.prompts import get_base_plan_prompt, get_advanced_planner_prompt, get_plan_markdown_rules

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

    prompt_fields = _extract_prompt_fields(first_response_json)
    prompt_system = _build_prompt_system_from_fields(
        role=prompt_fields["role"],
        context=prompt_fields["context"]
    )
    prompt_user = prompt_fields["task"]

    logger.info(
        "Sequential Planning - first response converted to markdown (prompt_user_length=%d, sections=%d)",
        len(prompt_user),
        len(first_response_json.get("sections", []))
    )

    second_input_prompt = f"""
이전 분석 결과를 기반으로 상세 계획을 생성하세요:

{prompt_user}

위 분석 결과를 참고하여, 다음 구조의 JSON으로 최종 보고서 계획을 생성하세요:
{{
    "title": "보고서 제목",
    "date": "2025.10.01",
    "sections": [
        {{
            "section_name": "BACKGROUND",
            "title": "배경 제목",
            "description": "배경 설명 (3문장)",
            "order": 1
        }},
        {{
            "section_name": "MAIN_CONTENT",
            "title": "섹션 제목",
            "description": "섹션 설명",
            "order": 2
        }},
        {{
            "section_name": "SUMMARY",
            "title": "요약 제목",
            "description": "요약 설명",
            "order": 3
        }}{{
            "section_name": "CONCLUSION",
            "title": "결론 제목",
            "description": "결론 설명",
            "order": 4
        }}
    ],
    "estimated_word_count": 5000,
    "estimated_sections_count": 5
}}

응답은 반드시 유효한 JSON만 포함하세요. Markdown 형식이나 추가 설명은 불가합니다.
"""
    second_response = await _call_sequential_planning(
        second_input_prompt,
        is_web_search=is_web_search,
        system_prompt=prompt_system
    )

    logger.info("Sequential Planning - second API call completed")

    plan_dict = _parse_plan_response(second_response)
    plan_dict["prompt_user"] = prompt_user
    plan_dict["prompt_system"] = prompt_system

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
                user_prompt=prompt_user,
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
    input_prompt: str,
    is_web_search: bool = False,
    system_prompt: Optional[str] = None
) -> str:
    """
    Claude API를 호출하여 Sequential Planning 실행

    Args:
        input_prompt: 입력 프롬프트
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
                "content": input_prompt
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

        # JSON 파싱
        plan_json = json.loads(cleaned_text)

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
    estimated_word_count = plan_json.get("estimated_word_count", 0)

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
        "formality": emotional_needs_raw.get("formality", "professional"),
        "confidence_level": emotional_needs_raw.get("confidence_level", "medium"),
        "decision_focus": emotional_needs_raw.get("decision_focus", "strategic")
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

    output_structure = (
        restructured.get("output_structure")
        or first_response_json.get("context")
        or first_response_json.get("framework")
    )

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
        "output_structure": output_structure,
        "task": task
    }


def _build_prompt_system_from_fields(role: str, context: str) -> str:
    """
    role/context를 system prompt 상단에 반영하고 기본 마크다운 규칙을 이어붙인다.
    """
    role_text = role or "전문가"
    context_text = context or "맥락 정보가 제공되지 않았습니다."

    return f"""{role_text}

# 맥락
{context_text}

## 마크다운 작성 규칙
{get_plan_markdown_rules()}"""
