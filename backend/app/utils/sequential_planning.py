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
    is_template_used: bool = True
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
    start_time = time.time()

    # 1. 입력 검증
    if not topic or not isinstance(topic, str):
        raise ValueError("topic is required and must be a string")

    if len(topic) > 200:
        raise ValueError("topic must be less than 200 characters")

    logger.info(f"Sequential Planning started - topic={topic}, template_id={template_id}")

    try:
        # 2. Single-step or two-step planning based on is_template_used parameter
        if is_template_used:
            # Single-step: Traditional template-based planning
            guidance_prompt = get_base_plan_prompt()
            input_prompt = f"""요청 주제: {topic} {guidance_prompt} """

            # Single API call
            plan_response = await _call_sequential_planning(
                input_prompt,
                is_web_search=is_web_search
            )

            # Parse response
            plan_dict = _parse_plan_response(plan_response)

            elapsed = time.time() - start_time
            logger.info(f"Sequential Planning (single-step) completed - elapsed={elapsed:.2f}s, sections={len(plan_dict['sections'])}")

            return plan_dict

        else:
            # Two-step: Advanced Role Planner with 2-stage API calling
            logger.info("Sequential Planning (two-step) started - using Advanced Role Planner")

            # Step 1: First API call with ADVANCED_PLANNER_PROMPT
            advanced_prompt = get_advanced_planner_prompt()
            advanced_prompt = advanced_prompt.replace("{{USER_TOPIC}}", topic)
            first_input_prompt = advanced_prompt

            first_response = await _call_sequential_planning(
                first_input_prompt,
                is_web_search=is_web_search
            )

            logger.info(f"Sequential Planning - first API call completed")

            # Step 2: Convert first response to markdown for prompt_user
            first_response_json = json.loads(_extract_json_from_response(first_response))
            prompt_user = _build_prompt_user_from_first_response(first_response_json)

            logger.info(f"Sequential Planning - first response converted to markdown (prompt_user)")

            # Step 3: Second API call with prompt_user included
            second_input_prompt = f"""
이전 분석 결과를 기반으로 상세 계획을 생성하세요:

{prompt_user}

위 분석 결과를 참고하여, 다음 구조의 JSON으로 최종 보고서 계획을 생성하세요:
{{
    "title": "보고서 제목",
    "sections": [
        {{
            "title": "섹션 제목",
            "description": "섹션 설명 (1문장)",
            "key_points": ["포인트1", "포인트2", "포인트3"],
            "order": 1
        }},
        ...
    ],
    "estimated_word_count": 5000,
    "estimated_sections_count": 5
}}

응답은 반드시 유효한 JSON만 포함하세요. Markdown 형식이나 추가 설명은 불가합니다.
"""

            second_response = await _call_sequential_planning(
                second_input_prompt,
                is_web_search=is_web_search
            )

            logger.info(f"Sequential Planning - second API call completed")

            # Step 4: Parse second response
            plan_dict = _parse_plan_response(second_response)

            # Step 5: Add prompt_user and prompt_system to response
            plan_dict["prompt_user"] = prompt_user
            plan_dict["prompt_system"] = get_plan_markdown_rules()

            elapsed = time.time() - start_time
            logger.info(f"Sequential Planning (two-step) completed - elapsed={elapsed:.2f}s, sections={len(plan_dict['sections'])}")

            return plan_dict

    except Exception as e:
        logger.error(f"Sequential Planning failed - error={str(e)}", exc_info=True)
        raise SequentialPlanningError(f"Failed to generate plan: {str(e)}")

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
    is_web_search: bool = False
) -> str:
    """
    Claude API를 호출하여 Sequential Planning 실행

    Args:
        input_prompt: 입력 프롬프트
        is_web_search: Claude 웹 검색 활성화 여부

    Returns:
        Claude API 응답 (JSON 문자열)

    Raises:
        SequentialPlanningError: API 호출 실패
    """
    try:
        logger.info(f"Calling Claude API for sequential planning - using fast model")

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
            system_prompt="You are an expert in creating structured report plans. Respond only with valid JSON.",
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


def _build_prompt_user_from_first_response(first_response_json: Dict[str, Any]) -> str:
    """
    첫 번째 API 응답 JSON을 마크다운으로 변환하여 prompt_user로 사용

    Role Planner 응답 (selected_role, framework, sections)을 마크다운 형식으로 변환합니다.

    Args:
        first_response_json: 첫 번째 Claude API 응답 JSON
        {
            "selected_role": "Financial Analyst",
            "framework": "Top-down Macro Analysis",
            "sections": [...]
        }

    Returns:
        str: 마크다운 형식의 prompt_user

    Examples:
        >>> response = {
        ...     "selected_role": "Financial Analyst",
        ...     "framework": "Top-down Macro Analysis",
        ...     "sections": [
        ...         {"title": "배경", "description": "...", "key_points": [...], "order": 1}
        ...     ]
        ... }
        >>> md = _build_prompt_user_from_first_response(response)
        >>> "선택된 역할" in md
        True
        >>> "프레임워크" in md
        True
    """
    selected_role = first_response_json.get("selected_role", "전문가")
    framework = first_response_json.get("framework", "분석 프레임워크")
    sections = first_response_json.get("sections", [])

    lines = [
        f"## 선택된 역할: {selected_role}",
        f"{selected_role} 관점에서 주제를 분석합니다.",
        "",
        f"## 프레임워크: {framework}",
        f"{framework}을(를) 기반으로 분석합니다.",
        "",
    ]

    # 섹션별 계획 추가
    for idx, section in enumerate(sections, 1):
        section_title = section.get("title", f"섹션 {idx}")
        description = section.get("description", "")
        key_points = section.get("key_points", [])

        lines.append(f"## 섹션 {idx}: {section_title}")

        if description:
            lines.append(description)
            lines.append("")

        if key_points:
            lines.append("주요 포인트:")
            for point in key_points:
                lines.append(f"- {point}")
            lines.append("")

    return "\n".join(lines)
