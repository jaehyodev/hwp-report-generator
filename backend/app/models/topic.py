"""
Topic models for chat-based report system.

A topic represents a conversation thread about a specific report subject.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from shared.types.enums import TopicStatus, TopicSourceType


class TopicCreate(BaseModel):
    """Request model for creating a new topic.

    Attributes:
        input_prompt: User's original input describing the report subject
        language: Primary language for the report (default: 'ko')
        template_id: Optional template ID to use for dynamic system prompt generation
        prompt_user: Optional first step API response converted to markdown (from sequential_planning)
        prompt_system: Optional markdown rules for planning (from sequential_planning)
        source_type: Source type of the topic (template or basic) - REQUIRED
    """
    input_prompt: str = Field(..., min_length=1, max_length=1000, description="Report topic input")
    language: str = Field(default="ko", description="Primary language (ko/en)")
    template_id: Optional[int] = Field(default=None, description="Template ID for dynamic system prompt generation")
    prompt_user: Optional[str] = Field(default=None, description="First step API response converted to markdown (sequential_planning)")
    prompt_system: Optional[str] = Field(default=None, description="Markdown rules for planning (sequential_planning)")
    source_type: TopicSourceType = Field(..., description="Source type (template or basic)")


class TopicUpdate(BaseModel):
    """Request model for updating an existing topic.

    Attributes:
        generated_title: AI-generated title for the topic (optional)
        status: Topic status (active/archived/deleted) (optional)
    """
    generated_title: Optional[str] = Field(None, max_length=200, description="AI-generated title")
    status: Optional[TopicStatus] = Field(None, description="Topic status")


class Topic(BaseModel):
    """Full topic entity model.

    Attributes:
        id: Topic ID
        user_id: ID of the user who created the topic
        input_prompt: Original user input
        generated_title: AI-generated title (may be null initially)
        language: Primary language code
        status: Current topic status
        template_id: Optional template ID used for this topic
        prompt_user: Optional first step API response converted to markdown (from sequential_planning)
        prompt_system: Optional markdown rules for planning (from sequential_planning)
        source_type: Source type (template or basic) - IMMUTABLE
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: int
    user_id: int
    input_prompt: str
    generated_title: Optional[str] = None
    language: str = "ko"
    status: TopicStatus = TopicStatus.ACTIVE
    template_id: Optional[int] = None
    prompt_user: Optional[str] = None
    prompt_system: Optional[str] = None
    source_type: TopicSourceType = TopicSourceType.BASIC
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2  # Pydantic v2


class TopicResponse(BaseModel):
    """Public topic response model.

    Excludes internal fields. Suitable for API responses.

    Attributes:
        id: Topic ID
        input_prompt: Original user input
        generated_title: AI-generated title
        language: Primary language
        status: Topic status
        template_id: Optional template ID used for this topic
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: int
    input_prompt: str
    generated_title: Optional[str] = None
    language: str
    status: TopicStatus
    template_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TopicListResponse(BaseModel):
    """Paginated list of topics.

    Attributes:
        topics: List of topic responses
        total: Total number of topics
        page: Current page number
        page_size: Number of items per page
    """
    topics: list[TopicResponse]
    total: int
    page: int = 1
    page_size: int = 20


class TopicMessageRequest(BaseModel):
    """Request model for asking a question on a topic.

    Attributes:
        user_message: The user's message or question
        template_id: Optional template ID to use for dynamic system prompt generation
        selected_artifact_ids: Optional list of artifact IDs to include in context
    """
    user_message: str = Field(..., min_length=1, max_length=5000)
    template_id: Optional[int] = Field(None, description="사용할 템플릿 ID (선택)")
    selected_artifact_ids: Optional[list[int]] = Field(None, description="컨텍스트에 포함할 아티팩트 ID 목록")


# ============================================================
# Sequential Planning Models
# ============================================================

class PlanRequest(BaseModel):
    """POST /api/topics/plan 요청 모델

    Sequential Planning을 통한 보고서 계획 수립을 요청합니다.

    Attributes:
        topic: 보고서 주제 (필수, 최대 200자)
        template_id: 사용할 템플릿 ID (선택, None이면 default template 사용)
        is_web_search: 웹 검색 도구 사용 여부 (기본값: false)
        is_template_used: 템플릿 사용 여부 (기본값: true, false이면 template_id 무시)
    """
    topic: str = Field(..., min_length=1, max_length=200, description="보고서 주제")
    template_id: Optional[int] = Field(None, description="템플릿 ID (선택)")
    is_web_search: bool = Field(
        default=False,
        alias="isWebSearch",
        description="웹 검색 도구 사용 여부 (기본값: false)"
    )
    is_template_used: bool = Field(
        default=True,
        alias="isTemplateUsed",
        description="템플릿 사용 여부 (기본값: true, false이면 template_id 무시)"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "topic": "AI 시장 분석",
                "template_id": 1,
                "isWebSearch": True,
                "isTemplateUsed": True
            }
        }


class PlanSection(BaseModel):
    """보고서 계획의 섹션 정보

    Attributes:
        title: 섹션 제목
        description: 섹션 설명
        key_points: 섹션의 주요 포인트 목록
        order: 섹션 순서
    """
    title: str = Field(..., description="섹션 제목")
    description: str = Field(..., description="섹션 설명")
    key_points: Optional[list[str]] = Field(None, description="섹션 주요 포인트")
    order: int = Field(..., description="섹션 순서")


class PlanResponse(BaseModel):
    """POST /api/topics/plan 응답 모델

    Sequential Planning으로 생성된 보고서 계획을 반환합니다.

    Attributes:
        topic_id: 토픽 ID
        plan: 평문 형식의 계획 문서
    """
    topic_id: int
    plan: str


class GenerateRequest(BaseModel):
    """POST /api/topics/generate 요청 모델

    사용자가 승인한 계획을 바탕으로 보고서 생성을 시작합니다.

    Attributes:
        topic: 보고서 주제 (필수)
        plan: Sequential Planning에서 받은 계획 (필수)
        is_edit: messages DB에 plan 저장 여부 (선택, 기본값: false)
        is_web_search: 웹 검색 도구 사용 여부 (기본값: false)
    """
    topic: str = Field(..., min_length=1, max_length=200, description="보고서 주제")
    plan: str = Field(..., min_length=1, description="Sequential Planning에서 받은 계획")
    is_edit: bool = Field(
        default=False,
        alias="isEdit",
        description="messages DB에 plan 저장 여부 (기본값: false)"
    )
    is_web_search: bool = Field(
        default=False,
        alias="isWebSearch",
        description="웹 검색 도구 사용 여부 (기본값: false)"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "topic": "AI 시장 분석",
                "plan": "# 보고서 계획\n## 개요\n...",
                "isEdit": True,
                "isWebSearch": True
            }
        }


class GenerateResponse(BaseModel):
    """POST /api/topics/generate 또는 /ask 응답 모델 (202 Accepted)

    보고서 생성 또는 질문 응답이 백그라운드 task로 시작되었음을 알립니다.

    Attributes:
        topic_id: 토픽 ID
        status: 생성 상태 ("generating" 또는 "answering")
        message: 상태 메시지
        status_check_url: 진행 상황 확인 URL (/api/topics/{topic_id}/status)
        stream_url: SSE 스트림 URL (/api/topics/{topic_id}/status/stream)
    """
    topic_id: int
    status: str  # "generating" 또는 "answering"
    message: str
    status_check_url: str
    stream_url: str


class StatusResponse(BaseModel):
    """GET /api/topics/{id}/status 응답 모델

    보고서 생성의 현재 진행 상태를 반환합니다.

    Artifact 기반 상태 추적 (v2.5+ Option A):
    - 작업 시작 시: status="scheduled", file_path=NULL, progress=0
    - 작업 중: status="generating", file_path=NULL, progress=0-99
    - 완료 시: status="completed", file_path="s3://...", progress=100
    - 실패 시: status="failed", error_message="...", progress=0-99

    Attributes:
        topic_id: 토픽 ID
        artifact_id: 생성된 artifact ID
        status: 생성 상태 ("scheduled", "generating", "completed", "failed")
        progress_percent: 진행률 (0-100)
        current_step: 현재 진행 단계 (generating 중일 때만)
        started_at: 생성 시작 시간
        completed_at: 완료 시간 (completed일 때만)
        file_path: 파일 경로 (completed일 때만, 작업 중에는 NULL)
        error_message: 에러 메시지 (failed일 때만)
    """
    topic_id: int
    artifact_id: int
    status: str
    progress_percent: int
    current_step: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    file_path: Optional[str] = None  # NULL during work, populated at completion
    error_message: Optional[str] = None
