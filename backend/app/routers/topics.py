"""
Topic management API router.

Handles CRUD operations for topics (conversation threads).
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
import asyncio
import json
import time
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.models.user import User
from app.models.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    PlanRequest, PlanResponse,
    GenerateRequest, GenerateResponse,
    StatusResponse
)
from app.models.message import MessageCreate, MessageResponse, AskRequest
from app.models.artifact import ArtifactCreate, ArtifactResponse
from app.models.ai_usage import AiUsageCreate
from app.models.prompt_optimization import PromptOptimizationCreate, PromptOptimizationResponse
from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.database.ai_usage_db import AiUsageDB
from app.database.prompt_optimization_db import PromptOptimizationDB
from app.utils.auth import get_current_active_user
from app.utils.response_helper import success_response, error_response, ErrorCode
from shared.types.enums import TopicStatus, MessageRole, ArtifactKind, TopicSourceType
from app.utils.markdown_builder import build_report_md, build_report_md_from_json
from app.utils.file_utils import next_artifact_version, build_artifact_paths, write_text, sha256_of
from app.utils.claude_client import ClaudeClient
from app.utils.structured_client import StructuredClaudeClient
from app.utils.prompts import (
    create_topic_context_message,
    get_system_prompt,
    create_section_schema,
)
from app.utils.markdown_parser import parse_markdown_to_content
from app.utils.exceptions import InvalidTemplateError
from app.database.template_db import TemplateDB, PlaceholderDB

# Sequential Planning 관련 모듈
from app.utils.sequential_planning import sequential_planning, SequentialPlanningError, TimeoutError as SequentialPlanningTimeout
from fastapi.responses import StreamingResponse
from app.utils.prompt_optimizer import optimize_prompt_with_claude, map_optimized_to_claude_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topics", tags=["Topics"])

PROMPT_OPTIMIZATION_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_MD_CHARS = 30000
MAX_CONTEXT_CHARS = 50000
ARTIFACT_STATUS_GENERATING = "generating"
ARTIFACT_STATUS_COMPLETED = "completed"
ARTIFACT_STATUS_FAILED = "failed"


@dataclass
class SimpleMessage:
    role: MessageRole
    content: str
    seq_no: float


async def _get_topic_or_error(
    topic_id: int,
    current_user: User,
    *,
    allow_admin: bool = True,
    use_thread: bool = True
):
    """토픽을 조회하고 소유권/관리자 권한을 검증한다.

    Args:
        topic_id: 조회할 토픽 ID.
        current_user: 인증된 사용자 정보.
        allow_admin: True일 때 관리자에게 소유권 예외를 허용.
        use_thread: True면 DB 접근을 `asyncio.to_thread`로 감싸 이벤트 루프 블로킹을 피한다.

    Returns:
        tuple[Topic | None, dict | None]: (유효한 토픽 객체 또는 None, 실패 시 표준 에러 응답 또는 None).
    """
    if use_thread:
        topic = await asyncio.to_thread(TopicDB.get_topic_by_id, topic_id)
    else:
        topic = TopicDB.get_topic_by_id(topic_id)

    if not topic:
        return None, error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="주제를 찾을 수 없습니다."
        )

    if topic.user_id != current_user.id and not (allow_admin and getattr(current_user, "is_admin", False)):
        return None, error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 주제에 접근할 권한이 없습니다."
        )

    return topic, None


async def _build_section_schema(source_type, template_id: Optional[int]):
    """토픽의 source_type에 따라 Structured Outputs용 섹션 스키마를 생성한다.

    Args:
        source_type: TopicSourceType 또는 문자열(basic/template).
        template_id: template 모드일 때 placeholder를 로드하기 위한 템플릿 ID.

    Returns:
        dict | None: StructuredClaudeClient가 소비하는 섹션 스키마, 생성 불가 시 None.
    """
    source_type_str = source_type.value if hasattr(source_type, "value") else str(source_type)
    logger.info(f"[SCHEMA] Creating section schema - source_type={source_type_str}")

    if not source_type_str or source_type_str not in ("basic", "template"):
        logger.info("[SCHEMA] source_type not set, skipping section schema generation")
        return None

    try:
        if source_type_str == "template" and template_id:
            placeholders = await asyncio.to_thread(
                PlaceholderDB.get_placeholders_by_template,
                template_id
            )
            return await asyncio.to_thread(
                create_section_schema,
                source_type_str,
                placeholders
            )

        return await asyncio.to_thread(create_section_schema, "basic")

    except Exception as schema_error:
        logger.warning(
            f"[SCHEMA] Failed to create section schema - error={schema_error}",
            exc_info=True
        )
        return None


def _compose_system_prompt(
    prompt_user: Optional[str],
    prompt_system: Optional[str]
) -> Optional[str]:
    """Topic DB의 prompt_user와 prompt_system을 합성하여 system prompt 반환.

    Args:
        prompt_user: Sequential Planning 결과 (Optional)
        prompt_system: 마크다운 규칙 (Optional)

    Returns:
        str: 합성된 system_prompt (둘 다 NULL이면 None)

    Logic:
        1. 빈 문자열 제거 (strip 후 다시 None 체크)
        2. prompt_user, prompt_system 중 하나 이상 존재하면 '\n\n'으로 join
        3. 둘 다 NULL이면 None 반환
    """
    # 빈 문자열 처리 (strip 후 다시 None 체크)
    user_part = prompt_user.strip() if prompt_user else None
    system_part = prompt_system.strip() if prompt_system else None

    # 둘 다 없으면 None 반환
    if not user_part and not system_part:
        return None

    # 합성
    parts = []
    if user_part:
        parts.append(user_part)
    if system_part:
        parts.append(system_part)

    composed = "\n\n".join(parts)

    # 로깅
    logger.info(
        f"[COMPOSE_PROMPT] Composed system prompt - "
        f"user_part={len(user_part) if user_part else 0}B, "
        f"system_part={len(system_part) if system_part else 0}B, "
        f"total={len(composed)}B"
    )

    return composed


def _build_artifact_message(user_message: str, md_content: str, seq_no: float) -> SimpleMessage:
    """아티팩트 내용을 Claude 컨텍스트 메시지(SimpleMessage)로 변환한다.

    Args:
        user_message: 사용자 입력 메시지 내용.
        md_content: 포함할 MD 원문.
        seq_no: 컨텍스트 정렬에 사용할 seq 번호.

    Returns:
        SimpleMessage: Claude 메시지 포맷의 임시 사용자 메시지.
    """
    return SimpleMessage(
        role=MessageRole.USER,
        content=user_message,
        seq_no=seq_no
    )


class PromptOptimizationRequest(BaseModel):
    """프롬프트 고도화 입력 모델."""

    user_prompt: str = Field(..., min_length=10, max_length=5000, description="고도화할 사용자 프롬프트")


@router.post("", summary="Create a new topic")
async def create_topic(
    topic_data: TopicCreate,
    current_user: User = Depends(get_current_active_user)
):
    """새로운 주제(대화 스레드)를 생성합니다.

    요청 본문(Request Body):
        - input_prompt: 사용자가 입력한 보고서 주제 또는 설명 (필수)
        - language: 보고서의 기본 언어 (기본값: 'ko')

    반환(Returns):
        TopicResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - TOPIC.CREATION_FAILED: 주제 생성에 실패함
        - SERVER.DATABASE_ERROR: 데이터베이스 작업 중 오류 발생

    예시(Examples):
        요청(Request):  
        ```json
        {
        "input_prompt": "디지털뱅킹 트렌드 분석",
        "language": "ko"
        }
        ```

        응답(Response, 200):  
        ```json
        {
        "success": true,
        "data": {
            "id": 1,
            "input_prompt": "디지털뱅킹 트렌드 분석",
            "generated_title": null,
            "language": "ko",
            "status": "active",
            "created_at": "2025-10-28T10:30:00",
            "updated_at": "2025-10-28T10:30:00"
        },
        "error": null,
        "meta": {"requestId": "req_abc123"},
        "feedback": []
        }
        ```
    """

    try:
        topic = TopicDB.create_topic(current_user.id, topic_data)
        return success_response(TopicResponse.model_validate(topic))

    except Exception as e:
        return error_response(
            code=ErrorCode.TOPIC_CREATION_FAILED,
            http_status=500,
            message="주제 생성에 실패했습니다.",
            details={"error": str(e)},
            hint="잠시 후 다시 시도해주세요."
        )

@router.get("", summary="Get user's topics")
async def get_my_topics(
    status: Optional[TopicStatus] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_active_user)
):
    """현재 사용자의 주제(Topic) 목록을 페이지네이션 형태로 조회합니다.

    쿼리 파라미터(Query Parameters):
        - status: 주제 상태 필터 (active / archived / deleted) (선택)
        - page: 페이지 번호 (기본값: 1)
        - page_size: 페이지당 항목 수 (기본값: 20, 최대: 100)

    반환(Returns):
        TopicListResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    예시(Examples):
        요청(Request):  
        GET /api/topics?status=active&page=1&page_size=10

        응답(Response, 200):  
        ```json
        {
        "success": true,
        "data": {
            "topics": [...],
            "total": 25,
            "page": 1,
            "page_size": 10
        },
        "error": null,
        "meta": {"requestId": "req_def456"},
        "feedback": []
        }
        ```
    """


    try:
        # Validate page_size
        if page_size > 100:
            page_size = 100

        offset = (page - 1) * page_size
        topics, total = TopicDB.get_topics_by_user(
            user_id=current_user.id,
            status=status,
            limit=page_size,
            offset=offset
        )

        topic_responses = [TopicResponse.model_validate(t) for t in topics]
        result = TopicListResponse(
            topics=topic_responses,
            total=total,
            page=page,
            page_size=page_size
        )

        return success_response(result)

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_DATABASE_ERROR,
            http_status=500,
            message="주제 목록 조회에 실패했습니다.",
            details={"error": str(e)}
        )


@router.get("/{topic_id}", summary="Get topic by ID")
async def get_topic(
    topic_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """특정 주제(Topic) ID로 주제 정보를 조회합니다.

    경로 파라미터(Path Parameters):
        - topic_id: 조회할 주제의 ID

    반환(Returns):
        TopicResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - TOPIC.NOT_FOUND: 해당 주제를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 해당 주제에 대한 소유 권한이 없음

    예시(Examples):
        요청(Request):  
        GET /api/topics/1

        응답(Response, 200):  
        ```json
        {
        "success": true,
        "data": {
            "id": 1,
            "input_prompt": "디지털뱅킹 트렌드 분석",
            "generated_title": "2025 디지털뱅킹 트렌드 분석 보고서",
            "language": "ko",
            "status": "active",
            "created_at": "2025-10-28T10:30:00",
            "updated_at": "2025-10-28T10:35:00"
        },
        "error": null,
        "meta": {"requestId": "req_ghi789"},
        "feedback": []
        }
        ```
    """

    topic, error = await _get_topic_or_error(topic_id, current_user)
    if error:
        return error

    return success_response(TopicResponse.model_validate(topic))


@router.patch("/{topic_id}", summary="Update topic")
async def update_topic(
    topic_id: int,
    update_data: TopicUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """주제(Topic) 정보를 수정합니다.

    경로 파라미터(Path Parameters):
        - topic_id: 수정할 주제의 ID

    요청 본문(Request Body):
        - generated_title: AI가 생성한 제목 (선택)
        - status: 주제 상태 (active / archived / deleted) (선택)

    반환(Returns):
        수정된 TopicResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - TOPIC.NOT_FOUND: 해당 주제를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 해당 주제에 대한 소유 권한이 없음

    예시(Examples):
        요청(Request):  
        PATCH /api/topics/1  
        ```json
        {
        "generated_title": "2025 디지털뱅킹 트렌드 분석 보고서",
        "status": "archived"
        }
        ```

        응답(Response, 200):  
        ```json
        {
        "success": true,
        "data": {
            "id": 1,
            "generated_title": "2025 디지털뱅킹 트렌드 분석 보고서",
            "status": "archived",
            ...
        },
        "error": null,
        "meta": {"requestId": "req_jkl012"},
        "feedback": []
        }
        ```
    """

    topic, error = await _get_topic_or_error(topic_id, current_user)
    if error:
        return error

    try:
        updated_topic = TopicDB.update_topic(topic_id, update_data)
        return success_response(TopicResponse.model_validate(updated_topic))

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_DATABASE_ERROR,
            http_status=500,
            message="주제 수정에 실패했습니다.",
            details={"error": str(e)}
        )


@router.delete("/{topic_id}", summary="Delete topic")
async def delete_topic(
    topic_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """주제(Topic)를 삭제합니다. (하드 삭제 — 관련 메시지 및 아티팩트도 함께 삭제됨)

    경로 파라미터(Path Parameters):
        - topic_id: 삭제할 주제의 ID

    반환(Returns):
        성공 메시지를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - TOPIC.NOT_FOUND: 해당 주제를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 해당 주제에 대한 소유 권한이 없음

    ⚠️ 경고(Warning):
        이 작업은 **하드 삭제(Hard Delete)** 방식으로 수행됩니다.  
        해당 주제와 연결된 모든 메시지(messages), 아티팩트(artifacts),  
        그리고 AI 사용 기록(ai_usage)은 **영구적으로 삭제**됩니다.

    예시(Examples):
        요청(Request):  
        DELETE /api/topics/1

        응답(Response, 200):  
        ```json
        {
        "success": true,
        "data": {
            "message": "주제가 삭제되었습니다."
        },
        "error": null,
        "meta": {"requestId": "req_mno345"},
        "feedback": []
        }
        ```
    """

    topic, error = await _get_topic_or_error(topic_id, current_user)
    if error:
        return error

    try:
        deleted = TopicDB.delete_topic(topic_id)
        if deleted:
            return success_response({"message": "주제가 삭제되었습니다."})
        else:
            return error_response(
                code=ErrorCode.TOPIC_NOT_FOUND,
                http_status=404,
                message="주제를 찾을 수 없습니다."
            )

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_DATABASE_ERROR,
            http_status=500,
            message="주제 삭제에 실패했습니다.",
            details={"error": str(e)}
        )

@router.post("/{topic_id}/ask", summary="Ask question in conversation - Artifact state machine")
async def ask(
    topic_id: int,
    body: AskRequest,
    current_user: User = Depends(get_current_active_user)
):
    """대화(Conversation) 맵핑에서 질문을 수행합니다. - Artifact 상태 머신 패턴 적용

    매개변수(Args):
        - topic_id: 질문이 속한 주제의 ID
        - body: 요청 본문 (질문 내용 및 옵션 포함)
        - current_user: 인증된 사용자 정보

    반환(Returns):
        사용자 메시지(user_message), AI 응답(assistant_message),
        생성된 아티팩트(artifact), 토큰 사용 정보(usage)를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - TOPIC.NOT_FOUND: 해당 주제를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 해당 주제에 대한 소유 권한이 없음
        - VALIDATION.REQUIRED_FIELD: 입력 내용(content)이 비어 있음
        - ARTIFACT.NOT_FOUND: 지정된 아티팩트를 찾을 수 없음
        - ARTIFACT.INVALID_KIND: 해당 아티팩트는 MD 형식이 아님
        - ARTIFACT.UNAUTHORIZED: 다른 사용자의 아티팩트에 접근 시도
        - MESSAGE.CONTEXT_TOO_LARGE: 대화 컨텍스트 크기가 허용 한도를 초과함
        - TEMPLATE.NOT_FOUND: 지정된 템플릿을 찾을 수 없음
        - SERVER.SERVICE_UNAVAILABLE: Claude API 호출 실패
    """

    # === 1단계: 권한 및 검증 ===
    logger.info(f"[ASK] Start - topic_id={topic_id}, user_id={current_user.id}")

    topic, error = await _get_topic_or_error(topic_id, current_user)
    if error:
        logger.warning(f"[ASK] Topic validation failed - topic_id={topic_id}")
        return error

    # === Step 2: 조건부 template_id 검증 (source_type 기반) ===
    source_type_str = "basic"  # default
    if topic.source_type:
        source_type_str = topic.source_type.value if hasattr(topic.source_type, 'value') else str(topic.source_type)

    logger.info(f"[ASK] source_type detected - source_type={source_type_str}")

    if source_type_str == "template" and not topic.template_id:
        logger.warning(f"[ASK] Template required for source_type=template but missing - topic_id={topic_id}")
        return error_response(
            code=ErrorCode.TEMPLATE_NOT_FOUND,
            http_status=400,
            message="이 토픽에는 템플릿이 지정되어 있지 않습니다.",
            hint="source_type='template'인 토픽에는 템플릿이 반드시 필요합니다."
        )

    logger.info(f"[ASK] template_id validation passed - source_type={source_type_str}, template_id={topic.template_id}")

    content = (body.content or "").strip()
    if not content:
        logger.warning(f"[ASK] Empty content - topic_id={topic_id}")
        return error_response(
            code=ErrorCode.VALIDATION_REQUIRED_FIELD,
            http_status=400,
            message="입력 메시지가 비어있습니다.",
            hint="1자 이상 입력해주세요."
        )

    if len(content) > 50000:
        logger.warning(f"[ASK] Content too long - topic_id={topic_id}, length={len(content)}")
        return error_response(
            code=ErrorCode.VALIDATION_MAX_LENGTH_EXCEEDED,
            http_status=400,
            message="입력 메시지가 너무 깁니다.",
            hint="50,000자 이하로 입력해주세요."
        )

    # === 2단계: 사용자 메시지 저장 ===
    logger.info(f"[ASK] Saving user message - topic_id={topic_id}, length={len(content)}")
    user_msg = await asyncio.to_thread(
        MessageDB.create_message,
        topic_id,
        MessageCreate(role=MessageRole.USER, content=content)
    )
    logger.info(f"[ASK] User message saved - message_id={user_msg.id}, seq_no={user_msg.seq_no}")

    # === 3단계: 참조 문서 선택 ===
    reference_artifact = None
    if body.artifact_id is not None:
        logger.info(f"[ASK] Loading specified artifact - artifact_id={body.artifact_id}")
        reference_artifact = await asyncio.to_thread(
            ArtifactDB.get_artifact_by_id,
            body.artifact_id
        )

        if not reference_artifact:
            logger.warning(f"[ASK] Artifact not found - artifact_id={body.artifact_id}")
            return error_response(
                code=ErrorCode.ARTIFACT_NOT_FOUND,
                http_status=404,
                message="지정한 아티팩트를 찾을 수 없습니다."
            )

        if reference_artifact.topic_id != topic_id:
            logger.warning(f"[ASK] Artifact topic mismatch - artifact.topic_id={reference_artifact.topic_id}, request.topic_id={topic_id}")
            return error_response(
                code=ErrorCode.ARTIFACT_UNAUTHORIZED,
                http_status=403,
                message="이 아티팩트에 접근할 권한이 없습니다."
            )

        if reference_artifact.kind != ArtifactKind.MD:
            logger.warning(f"[ASK] Invalid artifact kind - artifact_id={body.artifact_id}, kind={reference_artifact.kind}")
            return error_response(
                code=ErrorCode.ARTIFACT_INVALID_KIND,
                http_status=400,
                message="MD 형식의 아티팩트만 참조할 수 있습니다.",
                details={"current_kind": reference_artifact.kind.value}
            )
    else:
        logger.info(f"[ASK] Loading latest MD artifact - topic_id={topic_id}")
        reference_artifact = await asyncio.to_thread(
            ArtifactDB.get_latest_artifact_by_kind,
            topic_id, ArtifactKind.MD, topic.language
        )
        if reference_artifact:
            logger.info(f"[ASK] Latest artifact found - artifact_id={reference_artifact.id}, version={reference_artifact.version}")
        else:
            logger.info(f"[ASK] No MD artifact found - proceeding without reference")

    # === 3.5단계: JSON 섹션 스키마 생성 (새로운 단계) ===
    section_schema = await _build_section_schema(topic.source_type, topic.template_id)

    # === 4단계: 컨텍스트 구성 ===
    logger.info(f"[ASK] Building context - topic_id={topic_id}")

    all_messages = await asyncio.to_thread(
        MessageDB.get_messages_by_topic,
        topic_id
    )
    logger.info(f"[ASK] Total messages in topic: {len(all_messages)}")

    # User 메시지 필터링
    user_messages = [m for m in all_messages if m.role == MessageRole.USER]

    # artifact_id가 **명시적으로** 지정된 경우에만, 해당 message 이전 것만 포함
    if body.artifact_id is not None and reference_artifact:
        ref_msg = await asyncio.to_thread(
            MessageDB.get_message_by_id,
            reference_artifact.message_id
        )
        if ref_msg:
            # reference message의 seq_no까지만 포함
            user_messages = [m for m in user_messages if m.seq_no <= ref_msg.seq_no]
            logger.info(f"[ASK] Filtered user messages by artifact - up_to_seq_no={ref_msg.seq_no}, count={len(user_messages)}")

    # 기존 max_messages 제한 (여전히 적용)
    if body.max_messages is not None:
        user_messages = user_messages[-body.max_messages:]

    logger.info(f"[ASK] User messages to include: {len(user_messages)}")

    # Assistant 메시지 필터링 (참조 문서 생성 메시지만)
    assistant_messages = []
    if reference_artifact:
        ref_msg = await asyncio.to_thread(
            MessageDB.get_message_by_id,
            reference_artifact.message_id
        )
        if ref_msg:
            assistant_messages = [ref_msg]
            logger.info(f"[ASK] Including reference assistant message - message_id={ref_msg.id}")

    # assistant 메시지 구성을 prompt에 구성하여 포함하게 함. 
    # 컨텍스트 배열 구성
    # context_messages = sorted(
    #     user_messages + assistant_messages,
    #     key=lambda m: m.seq_no
    # )


    # 최종 User message 구성
    user_message = _build_user_message_content(body.content, section_schema, ref_msg.content)

    claude_messages = [
        {"role": "user", "content": user_message}
    ]

    # TODO: 문서 내용 주입 정말 필요한지 재검토
    # 문서 내용 주입
    # if body.include_artifact_content and reference_artifact:
    #     logger.info(f"[ASK] Loading artifact content - artifact_id={reference_artifact.id}, path={reference_artifact.file_path}")

    #     try:
    #         with open(reference_artifact.file_path, 'r', encoding='utf-8') as f:
    #             md_content = f.read()

    #         original_length = len(md_content)
    #         if len(md_content) > MAX_MD_CHARS:
    #             md_content = md_content[:MAX_MD_CHARS] + "\n\n... (truncated)"
    #             logger.info(f"[ASK] Artifact content truncated - original={original_length}, truncated={MAX_MD_CHARS}")

    #         seq_no = context_messages[-1].seq_no + 0.5 if context_messages else 0
    #         artifact_msg = _build_artifact_message(content, md_content, seq_no)

    #         context_messages.append(artifact_msg)
    #         logger.info(f"[ASK] Artifact content injected - length={len(md_content)}")

    #     except Exception as e:
    #         logger.error(f"[ASK] Failed to load artifact content - error={str(e)}")
    #         return error_response(
    #             code=ErrorCode.ARTIFACT_DOWNLOAD_FAILED,
    #             http_status=500,
    #             message="아티팩트 파일을 읽을 수 없습니다.",
    #             details={"error": str(e)}
    #         )

    # Claude 메시지 배열 변환
    # claude_messages = [
    #     {"role": m.role.value, "content": m.content}
    #     for m in context_messages
    # ]

    # Topic context를 첫 번째 메시지로 추가
    topic_context_msg = create_topic_context_message(topic.input_prompt)
    claude_messages = [topic_context_msg] + claude_messages

    # 디버깅: 모든 메시지 내용 로깅 (각 메시지의 content 길이)
    for i, msg in enumerate(claude_messages):
        content_preview = msg.get("content", "")[:100] if isinstance(msg, dict) else str(msg)[:100]
        logger.info(f"[ASK] Message[{i}] - role={msg.get('role', 'N/A')}, length={len(msg.get('content', ''))}, preview={content_preview}")

    # 길이 검증
    total_chars = sum(len(msg["content"]) for msg in claude_messages)

    logger.info(f"[ASK] Context size - messages={len(claude_messages)}, total_chars={total_chars}, max={MAX_CONTEXT_CHARS}")

    if total_chars > MAX_CONTEXT_CHARS:
        logger.warning(f"[ASK] Context too large - total_chars={total_chars}")
        return error_response(
            code=ErrorCode.MESSAGE_CONTEXT_TOO_LARGE,
            http_status=400,
            message="컨텍스트 크기가 너무 큽니다.",
            details={"total_chars": total_chars, "max_chars": MAX_CONTEXT_CHARS},
            hint="max_messages를 줄이거나 include_artifact_content를 false로 설정해주세요."
        )

    # === 5단계: System Prompt 합성 (TopicDB 기반) ===
    system_prompt = _compose_system_prompt(
        prompt_user=topic.prompt_user,
        prompt_system=topic.prompt_system
    )

    if not system_prompt:
        logger.error(
            f"[ASK] prompt_user and prompt_system both NULL (required) - "
            f"topic_id={topic_id}, source_type={source_type_str}"
        )
        return error_response(
            code=ErrorCode.VALIDATION_REQUIRED_FIELD,
            http_status=400,
            message="이 토픽의 프롬프트가 설정되어 있지 않습니다.",
            hint="POST /api/topics/plan으로 계획을 먼저 생성해주세요."
        )

    logger.info(
        f"[ASK] Using composed system prompt from topic DB - "
        f"length={len(system_prompt)}B"
    )

    

    # === 6단계: Claude 호출 ===
    logger.info(f"[ASK] Calling Claude API - messages={len(claude_messages)}, use_json_schema={section_schema is not None}")

    json_converted = False  # ✅ 변수 초기화 (Step 7에서 사용됨)
    json_response = None  # ✅ JSON 응답 변수 초기화
    try:
        t0 = time.time()

        claude_client = ClaudeClient()

        # JSON 모드와 일반 모드 구분
        if section_schema:
            # JSON 모드: StructuredClaudeClient 사용 (Structured Outputs)
            logger.info(f"[ASK] Using Structured Outputs mode with section_schema")

            # source_type 추출
            source_type_str = "basic"
            if topic.source_type:
                source_type_str = topic.source_type.value if hasattr(topic.source_type, "value") else str(topic.source_type)

            # StructuredClaudeClient 호출
            structured_client = StructuredClaudeClient()

            # 메시지 배열을 context_messages로 변환 (dict 형식 유지)
            context_messages = [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in claude_messages
            ]

            json_response = await asyncio.to_thread(
                structured_client.generate_structured_report,
                topic=topic.generated_title if topic.generated_title else topic.input_prompt or "Report",
                system_prompt=system_prompt,
                section_schema=section_schema,
                source_type=source_type_str,
                context_messages=context_messages
            )

            # JSON 응답 처리 (항상 StructuredReportResponse 객체)
            logger.info(f"[ASK] JSON response received - sections={len(json_response.sections)}")
            markdown = await asyncio.to_thread(
                build_report_md_from_json,
                json_response
            )
            logger.info(f"[ASK] Converted JSON to markdown - length={len(markdown)}")
            input_tokens = structured_client.last_input_tokens
            output_tokens = structured_client.last_output_tokens

            # JSON 응답을 마크다운으로 변환했으므로, is_report = True로 강제 설정
            # (8단계에서 사용됨)
            json_converted = True
        else:
            # 일반 모드: chat_completion() 사용 (기존 방식)
            logger.info(f"[ASK] Using standard chat_completion mode")
            markdown, input_tokens, output_tokens = await asyncio.to_thread(
                claude_client.chat_completion,
                claude_messages,
                system_prompt,
                body.is_web_search
            )
            json_converted = False

        latency_ms = int((time.time() - t0) * 1000)

        logger.info(f"[ASK] Claude response received - input_tokens={input_tokens}, output_tokens={output_tokens}, latency_ms={latency_ms}")

    except Exception as e:
        logger.error(f"[ASK] Claude API call failed - error={str(e)}")
        return error_response(
            code=ErrorCode.SERVER_SERVICE_UNAVAILABLE,
            http_status=503,
            message="AI 응답 생성 중 오류가 발생했습니다.",
            details={"error": str(e)},
            hint="잠시 후 다시 시도해주세요."
        )

    # === 7단계: Assistant 메시지 저장 ===
    message_content = markdown
    logger.info(f"[ASK] Saving assistant message - topic_id={topic_id}, length={len(message_content)}")

    asst_msg = await asyncio.to_thread(
        MessageDB.create_message,
        topic_id,
        MessageCreate(role=MessageRole.ASSISTANT, content=message_content)
    )

    logger.info(f"[ASK] Assistant message saved - message_id={asst_msg.id}, seq_no={asst_msg.seq_no}")

    # === 8단계: MD artifact 저장 ===
    artifact = None

    logger.info(f"[ASK] Saving MD artifact")

    try:
        # Step 1: 버전 계산
        version = await asyncio.to_thread(
            next_artifact_version,
            topic_id, ArtifactKind.MD, topic.language
        )
        logger.info(f"[ASK] Artifact version - version={version}")

        # Step 2: 파일 경로 생성
        base_dir, md_path = await asyncio.to_thread(
            build_artifact_paths,
            topic_id, version, "report.md"
        )
        logger.info(f"[ASK] Artifact path - path={md_path}")

        # Step 3: 파일 저장
        bytes_written = await asyncio.to_thread(write_text, md_path, markdown)
        file_hash = await asyncio.to_thread(sha256_of, md_path)
        logger.info(f"[ASK] File written - size={bytes_written}, hash={file_hash[:16]}...")

        # Step 4: Artifact DB 레코드 생성
        artifact = await asyncio.to_thread(
            ArtifactDB.create_artifact,
            topic_id,
            asst_msg.id,
            ArtifactCreate(
                kind=ArtifactKind.MD,
                locale=topic.language,
                version=version,
                filename=md_path.name,
                file_path=str(md_path),
                file_size=bytes_written,
                sha256=file_hash,
                status=ARTIFACT_STATUS_COMPLETED,
                progress_percent=100,
                completed_at=datetime.utcnow().isoformat()
            )
        )
        logger.info(f"[ASK] Artifact created - artifact_id={artifact.id}, version={artifact.version}, status={artifact.status}")

        # === 8-1단계: 조건부 JSON artifact 저장 ===
        if json_converted and json_response:
            logger.info(f"[ASK] Saving JSON artifact from StructuredReportResponse - message_id={asst_msg.id}")

            try:
                # JSON 직렬화
                json_text = await asyncio.to_thread(
                    json_response.model_dump_json
                )
                logger.info(f"[ASK] JSON serialized - length={len(json_text)}")

                # JSON 파일 경로 생성
                json_filename = f"structured_{version}.json"
                _, json_path = await asyncio.to_thread(
                    build_artifact_paths,
                    topic_id, version, json_filename
                )
                logger.info(f"[ASK] JSON artifact path - path={json_path}")

                # JSON 파일 저장
                json_bytes_written = await asyncio.to_thread(write_text, json_path, json_text)
                json_file_hash = await asyncio.to_thread(sha256_of, json_path)
                logger.info(f"[ASK] JSON file written - size={json_bytes_written}, hash={json_file_hash[:16]}...")

                # JSON Artifact DB 레코드 생성
                json_artifact = await asyncio.to_thread(
                    ArtifactDB.create_artifact,
                    topic_id,
                    asst_msg.id,
                    ArtifactCreate(
                        kind=ArtifactKind.JSON,
                        locale=topic.language,
                        version=version,
                        filename=json_path.name,
                        file_path=str(json_path),
                        file_size=json_bytes_written,
                        sha256=json_file_hash,
                        status=ARTIFACT_STATUS_COMPLETED,
                        progress_percent=100,
                        completed_at=datetime.utcnow().isoformat()
                    )
                )
                logger.info(f"[ASK] JSON artifact created - artifact_id={json_artifact.id}, version={json_artifact.version}")

            except Exception as json_e:
                logger.error(f"[ASK] Failed to save JSON artifact - error={str(json_e)}")
                # JSON artifact 실패는 비치명적 - 계속 진행
        else:
            logger.info(f"[ASK] Skipping JSON artifact (json_converted={json_converted}, json_response={json_response is not None})")

    except Exception as e:
        logger.error(f"[ASK] Failed to save artifact - error={str(e)}")
        return error_response(
            code=ErrorCode.ARTIFACT_CREATION_FAILED,
            http_status=500,
            message="응답 파일 저장 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )

    # === 9단계: AI 사용량 저장 ===
    logger.info(f"[ASK] Saving AI usage - message_id={asst_msg.id}")

    try:
        await asyncio.to_thread(
            AiUsageDB.create_ai_usage,
            topic_id,
            asst_msg.id,
            AiUsageCreate(
                model=claude_client.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms
            )
        )

        logger.info(f"[ASK] AI usage saved")

    except Exception as e:
        logger.error(f"[ASK] Failed to save AI usage - error={str(e)}")
        # 사용량 저장 실패는 치명적이지 않으므로 계속 진행

    # === 10단계: 성공 응답 반환 ===
    logger.info(f"[ASK] Success - topic_id={topic_id}, has_artifact={artifact is not None}")

    return success_response({
        "topic_id": topic_id,
        "user_message": MessageResponse.model_validate(user_msg).model_dump(),
        "assistant_message": MessageResponse.model_validate(asst_msg).model_dump(),
        "artifact": ArtifactResponse.model_validate(artifact).model_dump() if artifact else None,
        "usage": {
            "model": claude_client.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms
        }
    })


# ============================================================
# Sequential Planning Endpoints
# ============================================================

@router.post("/plan", summary="Generate report plan with Sequential Planning", response_model=dict)
async def plan_report(
    request: PlanRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Sequential Planning을 이용한 보고서 계획 수립

    Template의 prompt_system을 활용하여 체계적인 보고서 계획을 생성합니다.

    응답시간 제약: 반드시 2초 이내

    Args:
        request: PlanRequest 모델
            - topic: 보고서 주제 (필수)
            - template_id: 템플릿 ID (선택)
        current_user: 인증된 사용자

    Returns:
        PlanResponse를 포함한 ApiResponse
    """
    start_time = time.time()

    try:
        logger.info(f"[PLAN] Started - topic='{request.topic}', template_id={request.template_id}, is_template_used={request.is_template_used}, user_id={current_user.id}")

        if request.is_template_used:
            p_template_id = request.template_id
        else:
            p_template_id = None  # 템플릿 미사용 시 None으로 설정

        source_type = TopicSourceType.TEMPLATE if request.is_template_used else TopicSourceType.BASIC

        topic_data = TopicCreate(
            input_prompt=request.topic,
            template_id=p_template_id if request.is_template_used else None,
            source_type=source_type
        ) 
        
        topic = TopicDB.create_topic(current_user.id, topic_data)
        logger.info(f"[PLAN] Topic created - topic_id={topic.id}")

        # Step 2. topic_id를 전달하여 Sequential Planning을 호출하고 실패 시 롤백
        try:
            plan_result = await sequential_planning(
                topic=request.topic,
                template_id=request.template_id,
                user_id=current_user.id,
                is_web_search=request.is_web_search,
                is_template_used=request.is_template_used,
                topic_id=topic.id
            )
        except Exception as planning_error:
            logger.error(f"[PLAN] Sequential Planning failed - topic_id={topic.id}, error={str(planning_error)}")
            TopicDB.delete_topic(topic.id)
            logger.info(f"[PLAN] Topic rolled back - topic_id={topic.id}")
            raise

        # Step 3. isTemplateUsed 값에 따른 조건부 prompt 저장
        if request.is_template_used:
            # 템플릿 기반 경로: Template의 prompt 정보 저장
            try:
                # 3-1. Template 조회
                template = TemplateDB.get_template_by_id(request.template_id)

                # 3-2. Template 존재 확인
                if template is None:
                    TopicDB.delete_topic(topic.id)
                    logger.warning(f"[PLAN] Template not found - template_id={request.template_id}")
                    return error_response(
                        message="템플릿을 찾을 수 없습니다.",
                        code=ErrorCode.RESOURCE_NOT_FOUND,
                        http_status=404,
                        details={"template_id": request.template_id}
                    )

                # 3-3. 권한 검증 (소유자 또는 admin)
                if template.user_id != current_user.id and current_user.role != 'admin':
                    TopicDB.delete_topic(topic.id)
                    logger.warning(f"[PLAN] Access denied - template_id={request.template_id}, user_id={current_user.id}")
                    return error_response(
                        message="이 템플릿에 접근할 수 없습니다.",
                        code=ErrorCode.ACCESS_DENIED,
                        http_status=403,
                        details={"template_id": request.template_id}
                    )

                # 3-4. prompt_user, prompt_system 저장
                try:
                    TopicDB.update_topic_prompts(
                        topic.id,
                        template.prompt_user,
                        template.prompt_system
                    )
                except Exception as e:
                    logger.warning(f"[PLAN] Update topic prompts failed (non-blocking) - topic_id={topic.id}, error={str(e)}")

            except Exception as e:
                logger.warning(f"[PLAN] Template-based prompt update failed (non-blocking) - topic_id={topic.id}, error={str(e)}")
        else:
            # 최적화 기반 경로: PromptOptimization 결과에서 user_prompt 저장
            try:
                # 3-1. PromptOptimization 결과 조회
                opt_result = PromptOptimizationDB.get_latest_by_topic(topic.id)

                if opt_result is None:
                    logger.warning(f"[PLAN] PromptOptimization result not found - topic_id={topic.id}")
                    prompt_user = None
                    prompt_system = None
                else:
                    prompt_user = opt_result.get('user_prompt')
                    prompt_system = opt_result.get('output_format')

                # 3-2. prompt_user, prompt_system (output_format) 저장
                try:
                    TopicDB.update_topic_prompts(
                        topic.id,
                        prompt_user,
                        prompt_system
                    )
                except Exception as e:
                    logger.warning(f"[PLAN] Update topic prompts failed (non-blocking) - topic_id={topic.id}, error={str(e)}")

            except Exception as e:
                logger.warning(f"[PLAN] Optimization-based prompt update failed (non-blocking) - topic_id={topic.id}, error={str(e)}")

        elapsed = time.time() - start_time
        logger.info(f"[PLAN] Completed - topic_id={topic.id}, elapsed={elapsed:.2f}s")

        return success_response(
            PlanResponse(
                topic_id=topic.id,
                plan=plan_result["plan"],
            )
        )

    except SequentialPlanningTimeout as e:
        logger.error(f"[PLAN] Timeout exceeded - error={str(e)}")
        return error_response(
            code=ErrorCode.REQUEST_TIMEOUT,
            http_status=504,
            message="보고서 계획 생성이 시간이 초과했습니다.",
            hint="나중에 다시 시도해주세요."
        )

    except SequentialPlanningError as e:
        logger.error(f"[PLAN] Planning failed - error={str(e)}", exc_info=True)
        return error_response(
            code=ErrorCode.REPORT_GENERATION_FAILED,
            http_status=500,
            message="보고서 계획 생성에 실패했습니다.",
            details={"error": str(e)}
        )

    except ValueError as e:
        logger.warning(f"[PLAN] Validation error - error={str(e)}")
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            http_status=400,
            message=str(e)
        )

    except Exception as e:
        logger.error(f"[PLAN] Unexpected error - error={str(e)}", exc_info=True)
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="보고서 계획 생성 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.post("/{topic_id}/generate", summary="Start background report generation", response_model=dict, status_code=202)
async def generate_report_background(
    topic_id: int,
    request: GenerateRequest,
    current_user: User = Depends(get_current_active_user),
    background_tasks = None
):
    """보고서 생성 시작 (백그라운드 asyncio task + Artifact 상태 관리)

    사용자가 승인한 계획을 바탕으로 보고서 생성을 백그라운드에서 시작합니다.
    Artifact을 즉시 생성하여 Frontend에서 진행 상황을 모니터링할 수 있습니다.
    
    Args:
        topic_id: 토픽 ID
        request: GenerateRequest 모델 (topic, plan, isWebSearch 만 포함)
        current_user: 인증된 사용자
        background_tasks: FastAPI background tasks (unused, use asyncio.create_task instead)

    Returns:
        202 Accepted - GenerateResponse 포함
    """
    start_time = time.time()

    try:
        logger.info(f"[GENERATE] Started - topic_id={topic_id}, user_id={current_user.id}")

        topic, error = await _get_topic_or_error(topic_id, current_user, use_thread=False)
        if error:
            logger.warning(f"[GENERATE] Topic validation failed - topic_id={topic_id}")
            return error

        if topic.source_type == TopicSourceType.TEMPLATE and not topic.template_id:
            logger.warning(f"[GENERATE] Template missing on template-based topic - topic_id={topic_id}")
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="이 토픽에는 템플릿이 지정되어 있지 않습니다.",
                hint="/api/topics/plan 호출 후 템플릿이 지정된 토픽을 사용해주세요."
            )

        template_id = topic.template_id

        # ✅ NEW: Artifact 즉시 생성 (status="scheduled", file_path=NULL)
        # ✅ CHANGED: kind를 HWPX에서 MD로 변경 (더 빠른 생성)
        logger.info(f"[GENERATE] Creating artifact - topic_id={topic_id}")
        
        artifact = await asyncio.to_thread(
            ArtifactDB.create_artifact,
            topic_id,
            None,  # message_id (background task이므로 None)
            ArtifactCreate(
                kind=ArtifactKind.MD,  # ✅ MD 파일로 즉시 생성
                locale="ko",
                version=1,
                filename="report.md",  # ✅ MD 파일명
                file_path=None,  # ✅ NULL during work
                file_size=0,
                status=ARTIFACT_STATUS_GENERATING,  # 즉시 generating 상태
                progress_percent=0,
                started_at=datetime.utcnow().isoformat()
            )
        )
        
        logger.info(f"[GENERATE] Artifact created - topic_id={topic_id}, artifact_id={artifact.id}")

        # 백그라운드 task 생성 (예외 처리 포함)
        task = asyncio.create_task(
            _background_generate_report(
                topic_id=topic_id,
                artifact_id=artifact.id,
                topic=request.topic,
                plan=request.plan,
                template_id=template_id,
                user_id=current_user.id,
                is_web_search=request.is_web_search
            )
        )

        # ✅ Task 예외 처리: 콜백에서는 빠르게 끝내기 (이벤트 루프 블로킹 금지)
        def handle_task_result(t: asyncio.Task):
            """Task 완료 콜백 - 상태 업데이트만 수행 (로깅 제거)

            이벤트 루프를 블로킹하면 다른 비동기 작업들이 대기하므로,
            콜백 내에서는 빠른 상태 업데이트만 수행하고
            로깅은 비동기로 따로 처리합니다.
            """
            exc = t.exception()
            if exc is not None and not isinstance(exc, asyncio.CancelledError):
                # 실패 상태 표시만 빠르게 수행 (DB 업데이트)
                try:
                    ArtifactDB.mark_failed(
                        artifact_id=artifact.id,
                        error_message=str(exc)[:500]
                    )
                except Exception:
                    pass  # 콜백 내 예외는 무시

            # 비동기 로깅 (이벤트 루프 블로킹 없음)
            async def log_task_completion():
                """Task 완료 후 로깅 (비동기)"""
                try:
                    await asyncio.sleep(0)  # 이벤트 루프 양보
                    if exc is not None:
                        if isinstance(exc, asyncio.CancelledError):
                            logger.warning(f"[BACKGROUND] Task cancelled - topic_id={topic_id}")
                        else:
                            logger.error(f"[BACKGROUND] Task failed - topic_id={topic_id}, error={str(exc)}")
                    else:
                        logger.info(f"[BACKGROUND] Task completed successfully - topic_id={topic_id}, artifact_id={artifact.id}")
                except Exception:
                    pass

            try:
                asyncio.create_task(log_task_completion())
            except RuntimeError:
                pass  # 이벤트 루프 없을 경우 무시

        task.add_done_callback(handle_task_result)

        elapsed = time.time() - start_time
        logger.info(f"[GENERATE] Task created - topic_id={topic_id}, artifact_id={artifact.id}, elapsed={elapsed:.2f}s")

        response_dict = success_response(
            GenerateResponse(
                topic_id=topic_id,
                status=ARTIFACT_STATUS_GENERATING,
                message="Report generation started in background",
                status_check_url=f"/api/topics/{topic_id}/status"
            ).model_dump()
        )
        return JSONResponse(content=response_dict, status_code=202)

    except Exception as e:
        logger.error(f"[GENERATE] Unexpected error - error={str(e)}", exc_info=True)
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="보고서 생성 시작 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.get("/{topic_id}/status", summary="Get report generation status (polling)", response_model=dict)
async def get_generation_status_endpoint(
    topic_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """보고서 생성 상태 조회 (폴링용) - Artifact 기반 상태 추적

    현재 보고서 생성의 진행 상태를 Artifact 테이블에서 조회합니다.
    
    ✅ 변경사항: MD artifact 상태 조회 (HWPX 대신)

    응답시간 제약: < 500ms

    Args:
        topic_id: 토픽 ID
        current_user: 인증된 사용자

    Returns:
        StatusResponse를 포함한 ApiResponse
    """
    try:
        topic, error = await _get_topic_or_error(topic_id, current_user)
        if error:
            logger.warning(f"[STATUS] Topic validation failed - topic_id={topic_id}")
            return error

        # ✅ CHANGED: Artifact 테이블에서 최신 MD artifact 조회 (HWPX 대신)
        logger.info(f"[STATUS] Querying artifact - topic_id={topic_id}")
        artifact = await asyncio.to_thread(
            ArtifactDB.get_latest_artifact_by_kind,
            topic_id,
            ArtifactKind.MD  # ✅ MD artifact로 변경
        )

        if artifact is None:
            logger.debug(f"[STATUS] No artifact found - topic_id={topic_id}")
            return error_response(
                code=ErrorCode.NOT_FOUND,
                http_status=404,
                message=f"토픽 {topic_id}의 생성 상태를 찾을 수 없습니다."
            )

        # ✅ StatusResponse 모델로 변환 (Artifact 데이터 매핑)
        response_data = StatusResponse(
            topic_id=topic_id,
            artifact_id=artifact.id,
            status=artifact.status,
            progress_percent=artifact.progress_percent,
            current_step=None,  # current_step은 legacy field, Artifact에는 없음
            started_at=artifact.started_at,
            completed_at=artifact.completed_at,
            file_path=artifact.file_path,  # ✅ 작업 중에는 NULL, 완료 시 populated
            error_message=artifact.error_message
        )

        logger.debug(f"[STATUS] Retrieved - topic_id={topic_id}, artifact_id={artifact.id}, status={artifact.status}, progress={artifact.progress_percent}%")

        return success_response(response_data)

    except Exception as e:
        logger.error(f"[STATUS] Unexpected error - error={str(e)}", exc_info=True)
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="상태 조회 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.get("/{topic_id}/status/stream", summary="Get completion notification stream (SSE)")
async def stream_generation_status(
    topic_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """보고서 생성 완료 알림 (SSE 스트림) - Artifact 기반 폴링
    
    ✅ 변경사항: MD artifact 상태 폴링 (HWPX 대신)

    클라이언트가 연결을 유지하면서 대기하다가 보고서 생성이 완료되면
    서버에서 이벤트를 푸시합니다.

    Args:
        topic_id: 토픽 ID
        current_user: 인증된 사용자

    Returns:
        SSE 스트림 응답 (text/event-stream)
    """
    topic, error = await _get_topic_or_error(topic_id, current_user)
    if error:
        logger.warning(f"[STREAM] Topic validation failed - topic_id={topic_id}")
        return error

    logger.info(f"[STREAM] Started - topic_id={topic_id}, user_id={current_user.id}")

    async def event_generator():
        """✅ SSE 이벤트 생성기 (Artifact 테이블 폴링)"""
        max_wait_time = 3600  # 1시간 타임아웃
        start_time = time.time()
        last_artifact = None
        check_interval = 0.5  # 0.5초마다 상태 확인

        try:
            while time.time() - start_time < max_wait_time:
                # ✅ CHANGED: Artifact 테이블에서 최신 MD artifact 조회 (HWPX 대신)
                artifact = await asyncio.to_thread(
                    ArtifactDB.get_latest_artifact_by_kind,
                    topic_id,
                    ArtifactKind.MD  # ✅ MD artifact로 변경
                )

                # Artifact가 없는 경우 (아직 생성되지 않음)
                if artifact is None:
                    await asyncio.sleep(check_interval)
                    continue

                # ✅ Artifact 상태가 변경되었으면 이벤트 발송
                if last_artifact is None or (
                    artifact.status != last_artifact.status or
                    artifact.progress_percent != last_artifact.progress_percent
                ):
                    # Status update 이벤트
                    event_data = {
                        "event": "status_update" if artifact.status == ARTIFACT_STATUS_GENERATING else "completion",
                        "artifact_id": artifact.id,
                        "status": artifact.status,
                        "progress_percent": artifact.progress_percent
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"

                    logger.debug(f"[STREAM] Event sent - topic_id={topic_id}, artifact_id={artifact.id}, event={event_data['event']}, progress={artifact.progress_percent}%")

                    last_artifact = artifact

                    # 완료 또는 실패 시 종료
                    if artifact.status in [ARTIFACT_STATUS_COMPLETED, ARTIFACT_STATUS_FAILED]:
                        # 최종 completion 이벤트
                        final_event = {
                            "event": "completion",
                            "artifact_id": artifact.id,
                            "status": artifact.status,
                            "file_path": artifact.file_path,
                            "error_message": artifact.error_message
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        logger.info(f"[STREAM] Final event sent - topic_id={topic_id}, artifact_id={artifact.id}, status={artifact.status}")
                        break

                # 상태 확인 대기
                await asyncio.sleep(check_interval)

        except asyncio.CancelledError:
            logger.info(f"[STREAM] Client disconnected - topic_id={topic_id}")
        except Exception as e:
            logger.error(f"[STREAM] Error in event generator - error={str(e)}", exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.post("/{topic_id}/optimize-prompt", summary="Optimize prompt for topic")
async def optimize_topic_prompt(
    topic_id: int,
    payload: PromptOptimizationRequest,
    current_user: User = Depends(get_current_active_user)
):
    """POST /api/topics/{topic_id}/optimize-prompt 프롬프트 고도화.

    Args:
        topic_id (int): 경로 파라미터에 포함된 토픽 ID.
        payload (PromptOptimizationRequest): 사용자가 입력한 원본 프롬프트.
        current_user (User): 인증된 사용자 정보.

    Returns:
        Dict[str, Any]: PromptOptimizationResponse를 담은 성공 응답.

    에러 코드:
        - TOPIC.NOT_FOUND (404): 토픽이 존재하지 않을 때.
        - TOPIC.UNAUTHORIZED (403): 토픽 소유자가 아닐 때.
        - PROMPT_OPTIMIZATION.TIMEOUT (504): Claude 호출이 타임아웃일 때.
        - PROMPT_OPTIMIZATION.ERROR (500): Claude 응답 처리 또는 DB 저장 실패.
    """

    normalized_prompt = payload.user_prompt.strip()
    masked_prompt = _mask_prompt_fragment(normalized_prompt)
    logger.info(
        "[PROMPT_OPTIMIZATION] Request received - topic_id=%s, user_id=%s, prompt=%s",
        topic_id,
        current_user.id,
        masked_prompt
    )

    topic, error = await _get_topic_or_error(
        topic_id,
        current_user,
        allow_admin=False,
        use_thread=False
    )
    if error:
        logger.warning(
            "[PROMPT_OPTIMIZATION] Topic validation failed - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id
        )
        return error

    try:
        # Claude 프롬프트 고도화 호출
        optimization_result = await optimize_prompt_with_claude(
            user_prompt=normalized_prompt,
            topic_id=topic_id,
            model=PROMPT_OPTIMIZATION_DEFAULT_MODEL
        )

        # Claude 응답을 PromptOptimizationCreate 모델로 래핑
        optimization_payload = PromptOptimizationCreate(
            user_prompt=normalized_prompt,
            hidden_intent=optimization_result.get("hidden_intent"),
            emotional_needs=optimization_result.get("emotional_needs"),
            underlying_purpose=optimization_result.get("underlying_purpose"),
            role=optimization_result.get("role"),
            context=optimization_result.get("context"),
            task=optimization_result.get("task"),
            model_name=PROMPT_OPTIMIZATION_DEFAULT_MODEL,
            latency_ms=optimization_result.get("latency_ms", 0)
        )

        # 고도화 결과를 DB에 저장
        record_id = PromptOptimizationDB.create(
            topic_id=topic_id,
            user_id=current_user.id,
            user_prompt=optimization_payload.user_prompt,
            hidden_intent=optimization_payload.hidden_intent,
            emotional_needs=optimization_payload.emotional_needs,
            underlying_purpose=optimization_payload.underlying_purpose,
            role=optimization_payload.role,
            context=optimization_payload.context,
            task=optimization_payload.task,
            model_name=optimization_payload.model_name,
            latency_ms=optimization_payload.latency_ms,
        )

        logger.info(
            "[PROMPT_OPTIMIZATION] Result stored - topic_id=%s, record_id=%s, latency_ms=%s",
            topic_id,
            record_id,
            optimization_payload.latency_ms
        )

        # 저장된 결과를 응답 모델로 변환
        created_record = PromptOptimizationDB.get_by_id(record_id)
        response_payload = _build_prompt_optimization_response(created_record)
        if response_payload is None:
            logger.error(
                "[PROMPT_OPTIMIZATION] Stored record missing - topic_id=%s, record_id=%s",
                topic_id,
                record_id
            )
            return error_response(
                code=ErrorCode.PROMPT_OPTIMIZATION_ERROR,
                http_status=500,
                message="프롬프트 고도화 결과 조회에 실패했습니다.",
                details={"recordId": record_id}
            )

        return success_response(response_payload)

    except TimeoutError:
        logger.error(
            "[PROMPT_OPTIMIZATION] Claude timeout - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id,
            exc_info=True
        )
        return error_response(
            code=ErrorCode.PROMPT_OPTIMIZATION_TIMEOUT,
            http_status=504,
            message="Claude 프롬프트 고도화가 제한 시간을 초과했습니다.",
            details={"topicId": topic_id}
        )

    except ValueError as exc:
        logger.error(
            "[PROMPT_OPTIMIZATION] Invalid response - topic_id=%s, user_id=%s, error=%s",
            topic_id,
            current_user.id,
            str(exc),
            exc_info=True
        )
        return error_response(
            code=ErrorCode.PROMPT_OPTIMIZATION_ERROR,
            http_status=500,
            message="Claude 프롬프트 고도화 응답 처리 중 오류가 발생했습니다.",
            details={"error": str(exc)}
        )

    except Exception as exc:
        logger.error(
            "[PROMPT_OPTIMIZATION] Unexpected error - topic_id=%s, user_id=%s, error=%s",
            topic_id,
            current_user.id,
            str(exc),
            exc_info=True
        )
        return error_response(
            code=ErrorCode.PROMPT_OPTIMIZATION_ERROR,
            http_status=500,
            message="프롬프트 고도화 요청 처리 중 오류가 발생했습니다.",
            details={"error": str(exc)}
        )

    finally:
        logger.info(
            "[PROMPT_OPTIMIZATION] Request finished - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id
        )


@router.get("/{topic_id}/optimization-result", summary="Get prompt optimization result")
async def get_prompt_optimization_result(
    topic_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """GET /api/topics/{topic_id}/optimization-result 최신 고도화 결과.

    Args:
        topic_id (int): 경로 파라미터 토픽 ID.
        current_user (User): 인증된 사용자.

    Returns:
        Dict[str, Any]: PromptOptimizationResponse 또는 data=None 포함 성공 응답.

    에러 코드:
        - TOPIC.NOT_FOUND (404): 토픽이 존재하지 않을 때.
        - TOPIC.UNAUTHORIZED (403): 토픽 소유자가 아닐 때.
    """

    logger.info(
        "[PROMPT_OPTIMIZATION] Result fetch requested - topic_id=%s, user_id=%s",
        topic_id,
        current_user.id
    )

    topic, error = await _get_topic_or_error(
        topic_id,
        current_user,
        allow_admin=False,
        use_thread=False
    )
    if error:
        logger.warning(
            "[PROMPT_OPTIMIZATION] Topic validation failed on fetch - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id
        )
        return error

    try:
        # 최신 고도화 결과 조회
        record = PromptOptimizationDB.get_latest_by_topic(topic_id)
        if not record:
            logger.info(
                "[PROMPT_OPTIMIZATION] No result yet - topic_id=%s, user_id=%s",
                topic_id,
                current_user.id
            )
            return success_response(data=None)

        response_payload = _build_prompt_optimization_response(record)
        return success_response(response_payload)

    except Exception as exc:
        logger.error(
            "[PROMPT_OPTIMIZATION] Fetch failed - topic_id=%s, user_id=%s, error=%s",
            topic_id,
            current_user.id,
            str(exc),
            exc_info=True
        )
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="프롬프트 고도화 결과 조회 중 오류가 발생했습니다.",
            details={"error": str(exc)}
        )

    finally:
        logger.info(
            "[PROMPT_OPTIMIZATION] Result fetch finished - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id
        )


def _build_prompt_optimization_response(record: Optional[Dict[str, Any]]) -> Optional[PromptOptimizationResponse]:
    """DB 행을 PromptOptimizationResponse로 변환한다."""

    if record is None:
        return None

    prepared: Dict[str, Any] = dict(record)
    emotional_needs = prepared.get("emotional_needs")

    # 감정적 니즈 JSON 문자열 역직렬화
    if isinstance(emotional_needs, str) and emotional_needs:
        try:
            prepared["emotional_needs"] = json.loads(emotional_needs)
        except json.JSONDecodeError:
            logger.warning(
                "[PROMPT_OPTIMIZATION] emotional_needs JSON parse failed - record_id=%s",
                prepared.get("id")
            )
            prepared["emotional_needs"] = None

    return PromptOptimizationResponse.model_validate(prepared)


def _mask_prompt_fragment(prompt: str, limit: int = 80) -> str:
    """민감정보를 보호하기 위해 프롬프트 일부만 로깅한다."""

    if not isinstance(prompt, str):
        return ""

    compact_prompt = " ".join(prompt.split())
    if len(compact_prompt) <= limit:
        return compact_prompt

    return f"{compact_prompt[:limit]}...({len(compact_prompt)}자)"


async def _background_generate_report(
    topic_id: int,
    artifact_id: int,
    topic: str,
    plan: str,
    template_id: Optional[int],
    user_id: str,
    is_web_search: bool = False
):
    """백그라운드에서 실제 보고서 생성 (Artifact 상태 관리)

    모든 동기 작업은 asyncio.to_thread()로 감싸져 event loop을 블로킹하지 않습니다.
    Artifact 상태를 점진적으로 업데이트합니다. MD 파일을 생성하고 저장합니다.

    Args:
        topic_id: 토픽 ID
        artifact_id: Artifact ID (상태 업데이트용)
        topic: 보고서 주제
        plan: Sequential Planning에서 받은 계획
        template_id: 템플릿 ID (source_type='template'일 때 필수, 'basic'일 때 선택)
        user_id: 사용자 ID
        is_web_search: Claude 웹 검색 활성화 여부
    """
    try:
        logger.info(f"[BACKGROUND] Report generation started - topic_id={topic_id}, artifact_id={artifact_id}")

        # === Step 0: Topic 정보 조회 (source_type 확인용) ===
        logger.info(f"[BACKGROUND] Fetching topic info - topic_id={topic_id}")
        topic_obj = await asyncio.to_thread(
            TopicDB.get_topic_by_id,
            topic_id
        )
        if not topic_obj:
            raise ValueError(f"Topic not found - topic_id={topic_id}")

        logger.info(f"[BACKGROUND] Topic loaded - source_type={topic_obj.source_type}")

        # source_type='template'인 경우 template_id 검증
        if topic_obj.source_type == TopicSourceType.TEMPLATE and not template_id:
            raise InvalidTemplateError(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="이 토픽은 template 기반이지만 template_id가 지정되지 않았습니다.",
                hint="토픽 생성 시 template_id를 지정해주세요."
            )

        # === Step 0.5: JSON 섹션 스키마 생성 (새로운 단계) ===
        section_schema = await _build_section_schema(topic_obj.source_type, topic_obj.template_id)

        # === Step 1: 진행 상태 업데이트 ===
        logger.info(f"[BACKGROUND] Preparing content - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status=ARTIFACT_STATUS_GENERATING,
            progress_percent=10
        )

        # === Step 2: Claude API 호출 (non-blocking) ===
        logger.info(f"[BACKGROUND] Calling Claude API - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status=ARTIFACT_STATUS_GENERATING,
            progress_percent=20
        )

        claude = ClaudeClient()

        # User prompt 구성
        user_prompt = _build_user_message_topic(topic, plan, section_schema)

        # === Step 2.5: System Prompt 합성 (TopicDB 기반) ===
        system_prompt = _compose_system_prompt(
            prompt_user=topic_obj.prompt_user,
            prompt_system=topic_obj.prompt_system
        )

        if not system_prompt:
            logger.warning(
                f"[BACKGROUND] prompt_user and prompt_system both NULL - "
                f"topic_id={topic_id}, using fallback system prompt"
            )
            system_prompt = await asyncio.to_thread(
                get_system_prompt,
                template_id=template_id,
                user_id=int(user_id) if isinstance(user_id, str) else user_id
            )
        else:
            logger.info(
                f"[BACKGROUND] Using composed system prompt from topic DB - "
                f"length={len(system_prompt)}B"
            )

        start_time = time.time()

        # JSON 모드와 일반 모드 구분
        json_converted = False  # ✅ 변수 초기화
        json_response = None  # ✅ JSON 응답 변수 초기화

        if section_schema:
            # JSON 모드: StructuredClaudeClient 사용 (Structured Outputs)
            logger.info(f"[BACKGROUND] Using Structured Outputs mode with section_schema")

            # source_type 추출
            source_type_str = topic_obj.source_type.value if hasattr(topic_obj.source_type, 'value') else str(topic_obj.source_type)

            # StructuredClaudeClient 호출
            structured_client = StructuredClaudeClient()

            # context_messages: 현재 topic 정보 기반으로 구성 (배경 생성이므로 기존 메시지 없음)
            context_messages = [
                {"role": "user", "content": user_prompt}
            ]

            json_response = await asyncio.to_thread(
                structured_client.generate_structured_report,
                topic=topic,
                system_prompt=system_prompt,
                section_schema=section_schema,
                source_type=source_type_str,
                context_messages=context_messages
            )

            # JSON 응답 처리 (항상 StructuredReportResponse 객체)
            logger.info(f"[BACKGROUND] JSON response received - sections={len(json_response.sections)}")
            markdown = await asyncio.to_thread(
                build_report_md_from_json,
                json_response
            )
            logger.info(f"[BACKGROUND] Converted JSON to markdown - length={len(markdown)}")
            json_converted = True
        else:
            # 일반 모드: generate_report() 사용 (section_schema 없음)
            logger.info(f"[BACKGROUND] Using standard mode without section_schema")
            markdown = await asyncio.to_thread(
                claude.generate_report,
                topic=topic,
                plan_text=user_prompt,
                system_prompt=system_prompt,
                isWebSearch=is_web_search
            )
            json_converted = False

        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = claude.last_input_tokens
        output_tokens = claude.last_output_tokens

        logger.info(f"[BACKGROUND] Content generated - topic_id={topic_id}, tokens={input_tokens}+{output_tokens}, json_converted={json_converted}")

        # === Step 3: 마크다운 파싱 및 변환 ===
        logger.info(f"[BACKGROUND] Parsing markdown - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status=ARTIFACT_STATUS_GENERATING,
            progress_percent=50
        )

        # === Step 4: MD 파일 저장 ===
        logger.info(f"[BACKGROUND] Saving MD file - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status=ARTIFACT_STATUS_GENERATING,
            progress_percent=70
        )

    
        # artifact_id로 받은 artifact를 조회해서 버전 사용
        artifact = await asyncio.to_thread(
            ArtifactDB.get_artifact_by_id,
            artifact_id
        )
        if not artifact:
            raise ValueError(f"Artifact not found - artifact_id={artifact_id}")

        md_version = artifact.version
        base_dir, md_path = build_artifact_paths(topic_id, md_version, "report.md")

        # ✅ Non-blocking: 파일 I/O를 스레드 끝에서 실행
        bytes_written = await asyncio.to_thread(
            write_text,
            md_path,
            markdown
        )
        file_hash = await asyncio.to_thread(
            sha256_of,
            md_path
        )

        logger.info(f"[BACKGROUND] MD file saved - topic_id={topic_id}, size={bytes_written}")

        # === Step 5: DB 저장 (메시지 + Artifact 업데이트) ===
        logger.info(f"[BACKGROUND] Saving to database Artifact - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status=ARTIFACT_STATUS_GENERATING,
            progress_percent=85
        )

        # ✅ Non-blocking: 메시지 생성을 스레드 끝에서 실행
        logger.info(f"[BACKGROUND] Saving to database Message - topic_id={topic_id}")
        assistant_msg = await asyncio.to_thread(
            MessageDB.create_message,
            topic_id,
            MessageCreate(role=MessageRole.ASSISTANT, content=markdown)
        )

        # ✅ Step 6: Artifact 상태 업데이트 + 파일 정보 추가 (완료)
        logger.info(f"[BACKGROUND] Updating artifact - topic_id={topic_id}, artifact_id={artifact_id}")
        completed_at = datetime.utcnow().isoformat()
        
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status=ARTIFACT_STATUS_COMPLETED,
            progress_percent=100,
            message_id=assistant_msg.id,
            file_path=str(md_path),  # ✅ MD 파일 경로 저장
            file_size=bytes_written,
            sha256=file_hash,
            completed_at=completed_at
        )

        # === Step 6-1: JSON artifact 저장 (JSON 변환 응답인 경우) ===
        if json_converted and json_response:
            json_version = next_artifact_version(topic_id, ArtifactKind.JSON, topic_obj.language)
            logger.info(f"[BACKGROUND] Saving JSON artifact from StructuredReportResponse - topic_id={topic_id} - json_version={json_version}")

            try:
                # Step 1: JSON 직렬화
                json_text = await asyncio.to_thread(
                    json_response.model_dump_json
                )
                logger.info(f"[BACKGROUND] JSON serialized - length={len(json_text)}")

                # Step 2: JSON 파일 경로 생성
                json_filename = f"structured_{json_version}.json"
                _, json_path = await asyncio.to_thread(
                    build_artifact_paths,
                    topic_id, json_version, json_filename
                )
                logger.info(f"[BACKGROUND] JSON artifact path - path={json_path}")

                # Step 3: JSON 파일 저장
                json_bytes_written = await asyncio.to_thread(write_text, json_path, json_text)
                json_file_hash = await asyncio.to_thread(sha256_of, json_path)
                logger.info(f"[BACKGROUND] JSON file written - size={json_bytes_written}, hash={json_file_hash[:16]}...")

                # Step 4: JSON Artifact DB 레코드 생성
                # 참고: message_id=None (백그라운드 생성이므로), json_version MD artifact와 동일
                json_artifact = await asyncio.to_thread(
                    ArtifactDB.create_artifact,
                    topic_id,
                    None,  # message_id=None (백그라운드 생성)
                    ArtifactCreate(
                        kind=ArtifactKind.JSON,
                        locale=topic_obj.language,
                        version=json_version,
                        filename=json_path.name,
                        file_path=str(json_path),
                        file_size=json_bytes_written,
                        sha256=json_file_hash,
                        status=ARTIFACT_STATUS_COMPLETED,
                        progress_percent=100,
                        completed_at=datetime.utcnow().isoformat()
                    )
                )

                logger.info(f"[BACKGROUND] JSON artifact created - artifact_id={json_artifact.id}, version={json_artifact.version}")

            except Exception as json_e:
                logger.error(f"[BACKGROUND] Failed to save JSON artifact - error={str(json_e)}")
                # JSON artifact 실패는 비치명적 - 계속 진행 (MD artifact는 이미 생성됨)
        else:
            logger.info(f"[BACKGROUND] Skipping JSON artifact (json_converted={json_converted}, json_response={json_response is not None})")

        # AI 사용량 저장 (non-critical, 실패 무시)
        try:
            await asyncio.to_thread(
                AiUsageDB.create_ai_usage,
                topic_id,
                assistant_msg.id,
                AiUsageCreate(
                    model=claude.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms
                )
            )
        except Exception as e:
            logger.error(f"[BACKGROUND] Failed to save AI usage - error={str(e)}")

        logger.info(f"[BACKGROUND] Report generation completed - topic_id={topic_id}, artifact_id={artifact_id}")

    except Exception as e:
        logger.error(f"[BACKGROUND] Report generation failed - topic_id={topic_id}, artifact_id={artifact_id}, error={str(e)}", exc_info=True)

        # ✅ Update Artifact status to failed
        try:
            await asyncio.to_thread(
                ArtifactDB.update_artifact_status,
                artifact_id=artifact_id,
                status=ARTIFACT_STATUS_FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow().isoformat()
            )
        except Exception as db_error:
            logger.error(f"[BACKGROUND] Failed to update artifact status - error={str(db_error)}")


def _build_user_message_topic(topic: str, plan: str ,section_schema: dict) -> str:
    """Claude에 전달할 User Message 빌드

    Args:
        topic: 보고서 주제
        section_schema: 섹션 스키마

    Returns:
        User message 문자열
    """
    sections_info = json.dumps(section_schema, ensure_ascii=False, indent=2)

    message = f"""당신은 구조화된 JSON 형식으로 보고서 섹션을 생성하는 전문가입니다.

# 보고서 주제: {topic}


## 보고서 작성 계획
{plan}

## 필수 섹션 메타정보

아래 섹션 정의를 따라 JSON 형식으로 보고서를 작성하세요:

{sections_info}

## 중요 지침
1. **반드시 JSON만 출력하세요** - 설명이나 주석 금지
3. **order 필드 정확성** - 섹션 순서를 order에 명시하세요
5. **모든 필수 섹션을 포함하세요** - 누락된 섹션이 없도록 확인

이제 위의 섹션 정의에 맞춰 JSON 형식의 보고서를 생성하세요."""

    return message

def _build_user_message_content( content: str, section_schema: dict, assitant_md: str) -> str:
    """Claude에 전달할 User Message 빌드

    Args:
        topic: 보고서 주제
        section_schema: 섹션 스키마

    Returns:
        User message 문자열
    """
    sections_info = json.dumps(section_schema, ensure_ascii=False, indent=2)

    message = f"""당신은 구조화된 JSON 형식으로 보고서를 생성하는 전문가입니다.

## 작업 목적
- 위 메시지들은 모두 참고용입니다.
- 아래에 제공된 ${{현재 보고서(MD) 원문}} 근거로 해서 **{content}** 의 요청에 맞는 JSON을 생성하세요.

## JSON 섹션 메타정보

{sections_info}

## ${{현재 보고서(MD) 원문}}
```markdown

{assitant_md}

```

"""
    return message
