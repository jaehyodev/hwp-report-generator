"""Claude 프롬프트 고도화 도우미 모듈."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from app.models.prompt_optimization import PromptOptimizationResponse
from app.utils.claude_client import ClaudeClient
from app.utils.prompts import PROMPT_OPTIMIZATION_PROMPT

logger = logging.getLogger(__name__)


async def optimize_prompt_with_claude(
    user_prompt: str,
    topic_id: int,
    model: str = "claude-sonnet-4-5-20250929"
) -> Dict[str, Any]:
    """사용자 프롬프트를 Claude에 전달하여 고도화 결과를 반환합니다.

    경로:
        backend/app/utils/prompt_optimizer.py::optimize_prompt_with_claude()

    설명:
        사용자의 원본 프롬프트를 Claude AI에 전달하여
        숨겨진 의도, 감정적 니즈, 목적, 역할, 맥락, 작업을 분석합니다.
        30초 타임아웃과 JSON 파싱을 포함합니다.

    파라미터:
        user_prompt: 사용자가 입력한 원본 프롬프트 문자열
        topic_id: 프롬프트와 연계된 토픽 ID
        model: 사용할 Claude 모델 이름

    반환:
        Claude가 반환한 고도화 정보와 지연 시간(ms)을 담은 딕셔너리:
        {
            "hidden_intent": str,
            "emotional_needs": Dict or None,
            "underlying_purpose": str,
            "role": str,
            "context": str,
            "task": str,
            "latency_ms": int
        }

    에러:
        TimeoutError: Claude 호출이 30초를 초과한 경우
        ValueError: 입력 값 또는 Claude JSON 응답이 잘못된 경우
        Exception: Claude API 자체에서 실패한 경우
    """

    # 기본 입력값 검증
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise ValueError("user_prompt는 비어 있지 않은 문자열이어야 합니다.")

    if not isinstance(topic_id, int):
        raise ValueError("topic_id는 정수여야 합니다.")

    if not isinstance(model, str) or not model.strip():
        raise ValueError("model은 비어 있지 않은 문자열이어야 합니다.")

    normalized_prompt = user_prompt.strip()
    model_name = model.strip()

    # 민감한 내용 보호를 위해 마스킹된 버전 로깅
    masked_prompt = mask_sensitive_prompt(normalized_prompt)
    logger.info("프롬프트 고도화 시작 - topic_id=%s, model=%s", topic_id, model_name)
    logger.info("입력 프롬프트(마스킹): %s", masked_prompt)

    try:
        claude_client = ClaudeClient()
    except Exception as exc:  # ClaudeClient 초기화 실패도 Claude API 오류로 간주
        logger.error("ClaudeClient 초기화 실패", exc_info=True)
        raise Exception("ClaudeClient 초기화에 실패했습니다.") from exc

    # 시스템 프롬프트에 사용자 입력 치환
    system_prompt = PROMPT_OPTIMIZATION_PROMPT.replace("{USER_PROMPT}", normalized_prompt)

    # Claude SDK 호출 파라미터 구성
    request_payload: Dict[str, Any] = {
        "model": model_name,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": normalized_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    # Claude 호출을 별도 스레드로 위임하여 asyncio.wait_for 타임아웃 제어
    async def _invoke_claude() -> Any:
        """Claude SDK 블로킹 호출을 비동기적으로 감싼다."""

        return await asyncio.to_thread(
            claude_client.client.messages.create,
            **request_payload
        )

    started = time.perf_counter()

    try:
        response = await asyncio.wait_for(_invoke_claude(), timeout=30)
    except asyncio.TimeoutError as exc:
        logger.error("Claude 프롬프트 고도화가 30초를 초과했습니다.", exc_info=True)
        raise TimeoutError("Claude prompt optimization timed out after 30 seconds") from exc
    except Exception as exc:
        logger.error("Claude 프롬프트 고도화 호출 실패", exc_info=True)
        raise Exception(f"Claude API 오류: {exc}") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)

    try:
        response_text = _extract_text_from_claude_response(response)
    except ValueError:
        logger.error("Claude 응답에서 텍스트를 추출하지 못했습니다.", exc_info=True)
        raise

    try:
        parsed_response = json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.error("Claude 응답 JSON 파싱 실패", exc_info=True)
        raise ValueError("Claude 응답을 JSON으로 파싱할 수 없습니다.") from exc

    if not isinstance(parsed_response, dict):
        logger.error(
            "Claude 응답 JSON 구조가 dict가 아닙니다: %s",
            type(parsed_response),
            exc_info=True,
        )
        raise ValueError("Claude 응답 JSON 구조가 올바르지 않습니다.")

    # 필수 필드 검증
    required_fields = ("hidden_intent", "underlying_purpose", "role", "context", "task")
    missing_fields = [
        field for field in required_fields
        if not isinstance(parsed_response.get(field), str) or not parsed_response[field].strip()
    ]

    if missing_fields:
        logger.error("Claude 응답에 필수 필드 누락: %s", missing_fields, exc_info=True)
        raise ValueError(f"필수 필드가 누락되었습니다: {', '.join(missing_fields)}")

    emotional_needs = parsed_response.get("emotional_needs")
    if emotional_needs is not None and not isinstance(emotional_needs, dict):
        logger.error(
            "emotional_needs 필드 타입 오류: %s",
            type(emotional_needs),
            exc_info=True,
        )
        raise ValueError("emotional_needs 필드는 객체 형태여야 합니다.")

    result = {
        "hidden_intent": parsed_response["hidden_intent"].strip(),
        "emotional_needs": emotional_needs,
        "underlying_purpose": parsed_response["underlying_purpose"].strip(),
        "role": parsed_response["role"].strip(),
        "context": parsed_response["context"].strip(),
        "task": parsed_response["task"].strip(),
        "latency_ms": latency_ms,
    }

    logger.info(
        "프롬프트 고도화 완료 - topic_id=%s, latency_ms=%s",
        topic_id,
        latency_ms,
    )

    return result


def map_optimized_to_claude_payload(
    optimization_result: PromptOptimizationResponse,
    original_user_prompt: str,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """고도화 결과를 Claude payload 형태로 매핑합니다.

    경로:
        backend/app/utils/prompt_optimizer.py::map_optimized_to_claude_payload()

    설명:
        고도화 결과(role, context, task, output_format)와 원본 프롬프트를
        Claude API 호출용 구조로 변환합니다.
        System 메시지: role + # CONTEXT 섹션 + output_format 
        User 메시지: task + 원래 요청

    파라미터:
        optimization_result: Claude가 반환한 고도화 결과 모델
        original_user_prompt: 사용자가 입력한 원본 프롬프트
        model: 재사용할 Claude 모델명 (없으면 optimization_result의 model_name)

    반환:
        Claude API 호출용 파라미터 딕셔너리:
        {
            "model": str,
            "system": str,
            "messages": List[Dict],
            "temperature": 0.1,
            "max_tokens": 4096
        }

    에러:
        ValueError: 필수 필드 또는 원본 프롬프트가 누락된 경우
    """

    logger.info("Claude payload 매핑 시작")

    if not isinstance(original_user_prompt, str) or not original_user_prompt.strip():
        raise ValueError("original_user_prompt는 비어 있지 않은 문자열이어야 합니다.")

    if optimization_result is None:
        raise ValueError("optimization_result가 필요합니다.")

    role = getattr(optimization_result, "role", None)
    context = getattr(optimization_result, "context", None)
    task = getattr(optimization_result, "task", None)
    output_format = getattr(optimization_result, "output_format", None)
    model_name = model.strip() if isinstance(model, str) and model.strip() else getattr(optimization_result, "model_name", None)

    for field_name, value in [("role", role), ("context", context), ("task", task)]:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} 필드가 비어 있습니다.")

    if not isinstance(model_name, str) or not model_name:
        raise ValueError("Claude 모델명이 설정되어야 합니다.")

    system_message = f"{role.strip()}\n\n# CONTEXT\n{context.strip()}\n## output_format\n{output_format.strip()}"
    user_message = (
        "아래 작업을 수행하세요:\n\n"
        f"{task.strip()}\n\n---\n\n"
        f"원래 요청: {original_user_prompt.strip()}"
    )

    payload: Dict[str, Any] = {
        "model": model_name,
        "system": system_message,
        "messages": [
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    logger.info("Claude payload 매핑 완료 - model=%s", model_name)

    return payload


def mask_sensitive_prompt(prompt: str, max_chars: int = 100) -> str:
    """로그 기록 시 민감 정보를 보호하기 위해 프롬프트를 축약합니다.

    경로:
        backend/app/utils/prompt_optimizer.py::mask_sensitive_prompt()

    설명:
        긴 프롬프트를 로그에 기록할 때 원본 길이를 유지하되
        처음 max_chars만 노출하고 나머지는 생략합니다.

    파라미터:
        prompt: 마스킹 대상 문자열
        max_chars: 로그에 그대로 노출할 최대 문자 수

    반환:
        길이 제한을 적용한 문자열 또는 마스킹된 문자열

    에러:
        ValueError: max_chars가 1 미만이거나 prompt가 문자열이 아닐 때
    """

    logger.info("프롬프트 마스킹 시작 - limit=%s", max_chars)

    if not isinstance(prompt, str):
        raise ValueError("prompt는 문자열이어야 합니다.")

    if not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars는 1 이상의 정수여야 합니다.")

    if len(prompt) <= max_chars:
        logger.info("프롬프트 마스킹 완료 - 길이 유지")
        return prompt

    logger.warning(
        "프롬프트 길이 초과 - original=%s, limit=%s",
        len(prompt),
        max_chars,
    )

    masked = f"{prompt[:max_chars]}...({len(prompt)}자)"
    logger.info("프롬프트 마스킹 완료 - 길이 축약")
    return masked


def _extract_text_from_claude_response(response: Any) -> str:
    """Claude 응답 객체에서 텍스트를 결합해 반환합니다.

    경로:
        backend/app/utils/prompt_optimizer.py::_extract_text_from_claude_response()

    설명:
        Anthropic SDK의 메시지 응답 객체에서 텍스트 블록을 추출합니다.

    파라미터:
        response: Anthropic messages.create 응답 객체

    반환:
        Claude가 반환한 텍스트 내용 (여러 블록은 줄바꿈으로 결합)

    에러:
        ValueError: 응답에 텍스트 블록이 없을 때
    """

    content_blocks = getattr(response, "content", None)
    if not content_blocks:
        raise ValueError("Claude 응답이 비어 있습니다.")

    texts: list = []

    # content 블록마다 텍스트를 추출
    for block in content_blocks:
        # Anthropic SDK 객체(text 속성) 또는 dict 형태 모두 처리
        block_text = getattr(block, "text", None)

        if isinstance(block_text, str) and block_text:
            texts.append(block_text)
            continue

        if isinstance(block, dict):
            dict_text = block.get("text")
            if isinstance(dict_text, str) and dict_text:
                texts.append(dict_text)
                continue

    if not texts:
        raise ValueError("Claude 응답에서 텍스트 블록을 찾지 못했습니다.")

    return "\n".join(texts).strip()
