"""Pydantic models for prompt optimization workflows."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class PromptOptimizationCreate(BaseModel):
    """Payload for creating a new prompt optimization entry.

    Attributes:
        user_prompt: Raw user prompt that needs optimization.
        hidden_intent: Implicit objective inferred from the prompt.
        emotional_needs: Emotional cues detected in the prompt.
        underlying_purpose: Business or functional purpose tied to the prompt.
        role: Persona or system role Claude should assume.
        context: Supplementary information relevant to the prompt.
        task: Specific instructions or tasks Claude must accomplish.
        model_name: Claude model identifier.
        latency_ms: Optional latency captured while processing.
    """

    model_config = ConfigDict(from_attributes=True)

    # 사용자 입력 프롬프트 본문
    user_prompt: str = Field(..., min_length=10, max_length=5000, description="고도화 요청 사용자 입력")
    # 숨겨진 의도 분석 결과
    hidden_intent: Optional[str] = Field(None, description="사용자가 드러내지 않은 실제 의도")
    # 감정적 니즈에 대한 분석 데이터
    emotional_needs: Optional[Dict[str, Any]] = Field(None, description="사용자가 원하는 정성적 니즈")
    # 프롬프트의 근본 목적 설명
    underlying_purpose: Optional[str] = Field(None, description="상위 목적 (전략/결정/분석 등)")
    # 모델에 부여할 역할
    role: str = Field(..., description="Claude에게 부여된 역할 설명")
    # 상황 또는 배경 정보
    context: str = Field(..., description="토픽 관련 시장/업무/환경 맥락")
    # 수행해야 할 구체적 작업
    task: str = Field(..., description="Claude가 수행해야 할 구조화된 작업 내용")
    # 사용할 Claude 모델 이름
    model_name: str = Field(default="claude-sonnet-4-5-20250929", description="사용된 Claude 모델명")
    # 처리 지연 시간 (밀리초)
    latency_ms: int = Field(default=0, description="Claude 호출 지연 시간 (ms)")


class PromptOptimizationResponse(BaseModel):
    """Response model for prompt optimization records exposed to clients.

    Attributes:
        id: Database identifier for the prompt optimization entry.
        topic_id: Related topic identifier when grouped.
        user_id: Owner of the prompt optimization entry.
        user_prompt: Raw user prompt.
        hidden_intent: Inferred hidden intent.
        emotional_needs: Emotional analysis payload.
        underlying_purpose: Purpose associated with the prompt.
        role: System or assistant role.
        context: Background context for the prompt.
        task: Desired task definition.
        model_name: Claude model name used for processing.
        latency_ms: Observed latency in milliseconds.
        created_at: Record creation timestamp.
        updated_at: Record last update timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    # 고유 식별자
    id: int = Field(..., description="고도화 결과 ID")
    # 관련 토픽 식별자
    topic_id: int = Field(..., description="관련 토픽 ID")
    # 소유 사용자 식별자
    user_id: int = Field(..., description="소유 사용자 ID")
    # 사용자 입력 프롬프트 본문
    user_prompt: str = Field(..., min_length=10, max_length=5000, description="고도화 요청 사용자 입력")
    # 숨겨진 의도 분석 결과
    hidden_intent: Optional[str] = Field(None, description="사용자가 드러내지 않은 실제 의도")
    # 감정적 니즈에 대한 분석 데이터
    emotional_needs: Optional[Dict[str, Any]] = Field(None, description="사용자가 원하는 정성적 니즈")
    # 프롬프트의 근본 목적 설명
    underlying_purpose: Optional[str] = Field(None, description="상위 목적 (전략/결정/분석 등)")
    # 모델에 부여할 역할
    role: str = Field(..., description="Claude에게 부여된 역할 설명")
    # 상황 또는 배경 정보
    context: str = Field(..., description="토픽 관련 시장/업무/환경 맥락")
    # 수행해야 할 구체적 작업
    task: str = Field(..., description="Claude가 수행해야 할 구조화된 작업 내용")
    # 사용할 Claude 모델 이름
    model_name: str = Field(default="claude-sonnet-4-5-20250929", description="사용된 Claude 모델명")
    # 처리 지연 시간 (밀리초)
    latency_ms: int = Field(default=0, description="Claude 호출 지연 시간 (ms)")
    # 생성 일시
    created_at: datetime = Field(..., description="생성 날짜")
    # 마지막 수정 일시
    updated_at: datetime = Field(..., description="수정 날짜")


class PromptOptimizationUpdate(BaseModel):
    """Payload for partially updating prompt optimization configurations.

    Attributes:
        role: Optionally override the Claude role.
        context: Optionally update contextual information.
        task: Optionally revise the task instructions.
        model_name: Optionally switch the Claude model.
    """

    model_config = ConfigDict(from_attributes=True)

    # 모델에 부여할 역할
    role: Optional[str] = Field(None, description="Claude에게 부여될 역할 설명")
    # 상황 또는 배경 정보
    context: Optional[str] = Field(None, description="토픽 관련 시장/업무/환경 맥락")
    # 수행해야 할 구체적 작업
    task: Optional[str] = Field(None, description="Claude가 수행해야 할 구조화된 작업 내용")
    # 사용할 Claude 모델 이름
    model_name: Optional[str] = Field(None, description="사용될 Claude 모델명")


class ClaudePayload(BaseModel):
    """Internal payload to interact with Claude completion API.

    Attributes:
        model: Claude model identifier.
        system: System message with role and context.
        messages: List of message dictionaries.
        temperature: Sampling temperature (0.1 for stability).
        max_tokens: Maximum output token count.
    """

    model_config = ConfigDict(from_attributes=True)

    # Claude 모델 이름
    model: str = Field(..., description="Claude API 호출용 모델명")
    # 시스템 프롬프트 (역할 + 맥락)
    system: str = Field(..., description="role과 context로 구성된 시스템 메시지")
    # 메시지 리스트
    messages: list = Field(..., description="Claude API에 전달할 메시지 배열")
    # 온도 설정 (낮을수록 일관성 있음)
    temperature: float = Field(default=0.1, description="Claude 응답의 창의성 정도")
    # 최대 토큰 수
    max_tokens: int = Field(default=4096, description="Claude 응답의 최대 토큰 수")
