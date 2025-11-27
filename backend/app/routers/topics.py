"""
Topic management API router.

Handles CRUD operations for topics (conversation threads).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import asyncio
import json
import time
import logging
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.user import User
from app.models.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    PlanRequest, PlanResponse, PlanSection,
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
from shared.types.enums import TopicStatus, MessageRole, ArtifactKind
from app.utils.markdown_builder import build_report_md
from app.utils.file_utils import next_artifact_version, build_artifact_paths, write_text, sha256_of
from app.utils.claude_client import ClaudeClient
from app.utils.prompts import (
    create_topic_context_message,
    get_system_prompt,
)
from app.utils.markdown_parser import parse_markdown_to_content
from app.utils.exceptions import InvalidTemplateError
from app.utils.response_detector import is_report_content, extract_question_content
from shared.constants import ProjectPath
from app.database.template_db import TemplateDB

# Sequential Planning 관련 모듈
from app.utils.sequential_planning import sequential_planning, SequentialPlanningError, TimeoutError as SequentialPlanningTimeout
from fastapi.responses import StreamingResponse
from app.utils.prompt_optimizer import optimize_prompt_with_claude, map_optimized_to_claude_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topics", tags=["Topics"])

PROMPT_OPTIMIZATION_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


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

    topic = TopicDB.get_topic_by_id(topic_id)

    if not topic:
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="주제를 찾을 수 없습니다.",
            hint="주제 ID를 확인해주세요."
        )

    # Check ownership
    if topic.user_id != current_user.id and not current_user.is_admin:
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 주제에 접근할 권한이 없습니다."
        )

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

    topic = TopicDB.get_topic_by_id(topic_id)

    if not topic:
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="주제를 찾을 수 없습니다."
        )

    # Check ownership
    if topic.user_id != current_user.id and not current_user.is_admin:
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 주제를 수정할 권한이 없습니다."
        )

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

    topic = TopicDB.get_topic_by_id(topic_id)

    if not topic:
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="주제를 찾을 수 없습니다."
        )

    # Check ownership
    if topic.user_id != current_user.id and not current_user.is_admin:
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 주제를 삭제할 권한이 없습니다."
        )

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


@router.post("/generate", summary="Generate topic report synchronously")
async def generate_topic_report(
    topic_data: TopicCreate,
    current_user: User = Depends(get_current_active_user)
):
    """토픽을 생성하고 즉시 보고서를 생성합니다."""

    input_prompt = (topic_data.input_prompt or "").strip()
    if not input_prompt:
        return error_response(
            code=ErrorCode.VALIDATION_REQUIRED_FIELD,
            http_status=400,
            message="입력 프롬프트가 비어있습니다.",
            hint="보고서 주제를 1자 이상 입력해주세요."
        )

    try:
        topic_payload = TopicCreate(
            input_prompt=input_prompt,
            language=topic_data.language,
            template_id=topic_data.template_id
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            http_status=400,
            message="요청 본문이 올바르지 않습니다.",
            details={"error": str(e)}
        )

    try:
        system_prompt = get_system_prompt(
            template_id=topic_data.template_id,
            user_id=current_user.id
        )
    except InvalidTemplateError as template_error:
        return error_response(
            code=template_error.code or ErrorCode.TEMPLATE_NOT_FOUND,
            http_status=template_error.http_status,
            message=template_error.message,
            hint=template_error.hint
        )

    try:
        topic = TopicDB.create_topic(current_user.id, topic_payload)
        user_msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.USER, content=input_prompt)
        )
        claude_client = ClaudeClient()
        claude_messages = [
            create_topic_context_message(input_prompt),
            {"role": "user", "content": input_prompt}
        ]

        start_time = time.time()
        try:
            response_text, input_tokens, output_tokens = claude_client.chat_completion(
                claude_messages,
                system_prompt=system_prompt,
                isWebSearch=False
            )
        except Exception as claude_error:
            logger.error(f"[GENERATE_SYNC] Claude error - {claude_error}")
            return error_response(
                code=ErrorCode.SERVER_SERVICE_UNAVAILABLE,
                http_status=503,
                message="AI 응답 생성 중 오류가 발생했습니다.",
                details={"error": str(claude_error)},
                hint="잠시 후 다시 시도해주세요."
            )
        latency_ms = int((time.time() - start_time) * 1000)

        parsed_content = parse_markdown_to_content(response_text)
        built_markdown = build_report_md(parsed_content)
        generated_title = parsed_content.get("title") or input_prompt

        TopicDB.update_topic(
            topic.id,
            TopicUpdate(generated_title=generated_title)
        )

        assistant_msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.ASSISTANT, content=built_markdown)
        )

        version = next_artifact_version(topic.id, ArtifactKind.MD, topic.language)
        _, md_path = build_artifact_paths(topic.id, version, "report.md")
        bytes_written = write_text(md_path, built_markdown)
        file_hash = sha256_of(md_path)
        completed_at = datetime.utcnow().isoformat()

        artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=assistant_msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                locale=topic.language,
                version=version,
                filename="report.md",
                file_path=str(md_path),
                file_size=bytes_written,
                sha256=file_hash,
                status="completed",
                progress_percent=100,
                started_at=completed_at,
                completed_at=completed_at
            )
        )

        try:
            AiUsageDB.create_ai_usage(
                topic.id,
                assistant_msg.id,
                AiUsageCreate(
                    model=claude_client.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms
                )
            )
        except Exception as usage_error:
            logger.error(f"[GENERATE_SYNC] Failed to save AI usage - error={usage_error}")

        return success_response({
            "topic_id": topic.id,
            "artifact_id": artifact.id,
            "message_id": assistant_msg.id,
            "user_message_id": user_msg.id
        })

    except Exception as e:
        logger.error(f"[GENERATE_SYNC] Failed to generate report - error={str(e)}", exc_info=True)
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="보고서 생성 중 오류가 발생했습니다.",
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

    topic = await asyncio.to_thread(TopicDB.get_topic_by_id, topic_id)
    if not topic:
        logger.warning(f"[ASK] Topic not found - topic_id={topic_id}")
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="토픽을 찾을 수 없습니다."
        )

    if topic.user_id != current_user.id and not current_user.is_admin:
        logger.warning(f"[ASK] Unauthorized - topic_id={topic_id}, owner={topic.user_id}, requester={current_user.id}")
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 토픽에 접근할 권한이 없습니다."
        )

    if not topic.template_id:
        logger.warning(f"[ASK] Template missing on topic - topic_id={topic_id}")
        return error_response(
            code=ErrorCode.TEMPLATE_NOT_FOUND,
            http_status=404,
            message="이 토픽에는 템플릿이 지정되어 있지 않습니다.",
            hint="계획을 먼저 생성 후 시도해 주세요."
        )

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

    # 컨텍스트 배열 구성
    context_messages = sorted(
        user_messages + assistant_messages,
        key=lambda m: m.seq_no
    )

    # 문서 내용 주입
    if body.include_artifact_content and reference_artifact:
        logger.info(f"[ASK] Loading artifact content - artifact_id={reference_artifact.id}, path={reference_artifact.file_path}")

        try:
            with open(reference_artifact.file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()

            original_length = len(md_content)
            MAX_MD_CHARS = 30000
            if len(md_content) > MAX_MD_CHARS:
                md_content = md_content[:MAX_MD_CHARS] + "\n\n... (truncated)"
                logger.info(f"[ASK] Artifact content truncated - original={original_length}, truncated={MAX_MD_CHARS}")

            # Create a temporary message-like object for artifact content
            class ArtifactMessage:
                def __init__(self, content, seq_no):
                    self.role = MessageRole.USER
                    self.content = content
                    self.seq_no = seq_no

            artifact_msg = ArtifactMessage(
                content=f"""{content}

현재 보고서(MD) 원문입니다. 개정 시 이를 기준으로 반영하세요.

```markdown
{md_content}
```""",
                seq_no=context_messages[-1].seq_no + 0.5 if context_messages else 0
            )

            context_messages.append(artifact_msg)
            logger.info(f"[ASK] Artifact content injected - length={len(md_content)}")

        except Exception as e:
            logger.error(f"[ASK] Failed to load artifact content - error={str(e)}")
            return error_response(
                code=ErrorCode.ARTIFACT_DOWNLOAD_FAILED,
                http_status=500,
                message="아티팩트 파일을 읽을 수 없습니다.",
                details={"error": str(e)}
            )

    # Claude 메시지 배열 변환
    claude_messages = [
        {"role": m.role.value, "content": m.content}
        for m in context_messages
    ]

    # Topic context를 첫 번째 메시지로 추가
    topic_context_msg = create_topic_context_message(topic.input_prompt)
    claude_messages = [topic_context_msg] + claude_messages

    user_message_content = user_msg.content

    logger.info(f"[ASK] Added topic context as first message - topic={topic.input_prompt}")
    logger.info(f"[ASK] Topic context message: {topic_context_msg}")

    # 디버깅: 모든 메시지 내용 로깅 (각 메시지의 content 길이)
    for i, msg in enumerate(claude_messages):
        content_preview = msg.get("content", "")[:100] if isinstance(msg, dict) else str(msg)[:100]
        logger.info(f"[ASK] Message[{i}] - role={msg.get('role', 'N/A')}, length={len(msg.get('content', ''))}, preview={content_preview}")

    # 길이 검증
    total_chars = sum(len(msg["content"]) for msg in claude_messages)
    MAX_CONTEXT_CHARS = 50000

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

    # === 4.5단계: 프롬프트 고도화 결과 확인 및 적용 ===
    optimized_system_prompt: Optional[str] = None

    try:
        logger.info(f"[ASK] Checking prompt optimization result - topic_id={topic_id}")
        optimization_record = await asyncio.to_thread(
            PromptOptimizationDB.get_latest_by_topic,
            topic_id
        )

        if optimization_record:
            optimization_response = _build_prompt_optimization_response(optimization_record)
            if optimization_response:
                optimization_payload = map_optimized_to_claude_payload(
                    optimization_response,
                    user_message_content,
                    PROMPT_OPTIMIZATION_DEFAULT_MODEL
                )

                optimized_system_prompt = optimization_payload.get("system")
                optimized_messages = optimization_payload.get("messages") or []
                if optimized_messages:
                    optimized_first_message = optimized_messages[0]
                    if claude_messages:
                        claude_messages[0] = optimized_first_message
                    else:
                        claude_messages = [optimized_first_message]

                logger.info("[ASK] Optimization result found - using optimized prompts")
    except Exception as optimization_error:
        logger.warning(
            f"[ASK] Failed to apply optimization result - error={optimization_error}",
            exc_info=True
        )

    # === 5단계: System Prompt 선택 (우선순위: template > default) ===
    if optimized_system_prompt is not None:
        system_prompt = optimized_system_prompt
    else:
        logger.info("[ASK] No optimization result - using default system prompt")
        logger.info(f"[ASK] Selecting system prompt - template_id={topic.template_id}")

        try:
            system_prompt = await asyncio.to_thread(
                get_system_prompt,
                custom_prompt=None,
                template_id=topic.template_id,
                user_id=current_user.id
            )
        except InvalidTemplateError as e:
            logger.warning(f"[ASK] Template error - code={e.code}, message={e.message}")
            return error_response(
                code=e.code,
                http_status=e.http_status,
                message=e.message,
                hint=e.hint
            )
        except ValueError as e:
            logger.error(f"[ASK] Invalid arguments - error={str(e)}")
            return error_response(
                code=ErrorCode.SERVER_INTERNAL_ERROR,
                http_status=500,
                message="시스템 오류가 발생했습니다.",
                details={"error": str(e)}
            )

    # === 6단계: Claude 호출 ===
    logger.info(f"[ASK] Calling Claude API - messages={len(claude_messages)}")

    try:
        t0 = time.time()

        claude_client = ClaudeClient()
        response_text, input_tokens, output_tokens = claude_client.chat_completion(
            claude_messages,
            system_prompt,
            isWebSearch=body.is_web_search
        )

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

    # === 7단계: 응답 형태 판별 ===
    logger.info(f"[ASK] Detecting response type")
    try:
        is_report = is_report_content(response_text)
    except Exception as detector_error:
        logger.warning(
            f"[ASK] Failed to detect response type, defaulting to report - error={detector_error}"
        )
        is_report = True

    logger.info(f"[ASK] Response type detected - is_report={is_report}")

    # === 7-1단계: 질문 응답일 경우 콘텐츠 추출 ===
    message_content = response_text
    if not is_report:
        logger.info(f"[ASK] Question response detected - extracting pure content")
        extracted_content = extract_question_content(response_text)

        if extracted_content:
            message_content = extracted_content
            logger.info(f"[ASK] Content extracted - original={len(response_text)} chars, extracted={len(extracted_content)} chars")
        else:
            logger.warning(f"[ASK] Question response but extraction returned empty, using original")

    # === 7-2단계: Assistant 메시지 저장 (항상 저장) ===
    logger.info(f"[ASK] Saving assistant message - topic_id={topic_id}, length={len(message_content)}")

    asst_msg = await asyncio.to_thread(
        MessageDB.create_message,
        topic_id,
        MessageCreate(role=MessageRole.ASSISTANT, content=message_content)
    )

    logger.info(f"[ASK] Assistant message saved - message_id={asst_msg.id}, seq_no={asst_msg.seq_no}")

    # === 8단계: 조건부 MD 파일 저장 (Artifact 상태 머신 패턴) ===
    artifact = None

    if is_report:
        logger.info(f"[ASK] Saving MD artifact (report content - Artifact state machine)")

        try:
            # Step 1: Markdown 파싱 및 제목 추출
            logger.info(f"[ASK] Parsing markdown content")
            result = await asyncio.to_thread(parse_markdown_to_content, response_text)
            generated_title = result.get("title") or "보고서"
            logger.info(f"[ASK] Parsed successfully - title={generated_title}")

            # Step 2: 마크다운 빌드
            md_text = await asyncio.to_thread(build_report_md, result)
            logger.info(f"[ASK] Built markdown - length={len(md_text)}")

            # Step 3: 버전 계산
            version = await asyncio.to_thread(
                next_artifact_version,
                topic_id, ArtifactKind.MD, topic.language
            )
            logger.info(f"[ASK] Artifact version - version={version}")

            # Step 4: 파일 경로 생성
            base_dir, md_path = await asyncio.to_thread(
                build_artifact_paths,
                topic_id, version, "report.md"
            )
            logger.info(f"[ASK] Artifact path - path={md_path}")

            # Step 5: 파일 저장 (파싱된 마크다운만)
            bytes_written = await asyncio.to_thread(write_text, md_path, md_text)
            file_hash = await asyncio.to_thread(sha256_of, md_path)

            logger.info(f"[ASK] File written - size={bytes_written}, hash={file_hash[:16]}...")

            # ✅ Step 6: Artifact DB 레코드 생성 (status="completed" + 모든 파일 정보 포함)
            artifact = await asyncio.to_thread(
                ArtifactDB.create_artifact,
                topic_id,
                asst_msg.id,
                ArtifactCreate(
                    kind=ArtifactKind.MD,
                    locale=topic.language,
                    version=version,
                    filename=md_path.name,
                    file_path=str(md_path),  # ✅ 완료 상태로 파일 정보 완전히 populated
                    file_size=bytes_written,
                    sha256=file_hash,
                    status="completed",  # ✅ 명시적으로 completed 상태
                    progress_percent=100,  # ✅ 100% 완료
                    completed_at=datetime.utcnow().isoformat()  # ✅ 완료 시간 기록
                )
            )

            logger.info(f"[ASK] Artifact created - artifact_id={artifact.id}, version={artifact.version}, status={artifact.status}")

        except Exception as e:
            logger.error(f"[ASK] Failed to save artifact - error={str(e)}")
            return error_response(
                code=ErrorCode.ARTIFACT_CREATION_FAILED,
                http_status=500,
                message="응답 파일 저장 중 오류가 발생했습니다.",
                details={"error": str(e)}
            )
    else:
        logger.info(f"[ASK] No artifact created (question/conversation response)")

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

        topic_data = TopicCreate(
                input_prompt=request.topic,
                template_id=p_template_id
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

        # Step 3. 템플릿 미사용 케이스는 plan_result 기반 프롬프트를 Topic에 반영
        # 템플릿 기반 플로우는 프롬프트가 고정되어 있으므로 저장 불필요
        # if request.is_template_used:
        #     # 템플릿 기반 플로우는 추가 프롬프트 저장이 필요 없음
        #     pass
        # else:
        #     TopicDB.update_topic_prompts(
        #         topic.id,
        #         plan_result.get("prompt_user"),
        #         plan_result.get("prompt_system")
        #     )

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

        # Topic 조회 및 권한 확인
        topic = TopicDB.get_topic_by_id(topic_id)
        if not topic:
            logger.warning(f"[GENERATE] Topic not found - topic_id={topic_id}")
            return error_response(
                code=ErrorCode.TOPIC_NOT_FOUND,
                http_status=404,
                message="토픽을 찾을 수 없습니다."
            )

        if topic.user_id != current_user.id and not current_user.is_admin:
            logger.warning(f"[GENERATE] Unauthorized - topic_id={topic_id}, owner={topic.user_id}, requester={current_user.id}")
            return error_response(
                code=ErrorCode.TOPIC_UNAUTHORIZED,
                http_status=403,
                message="이 토픽에 접근할 권한이 없습니다."
            )

        if not topic.template_id:
            logger.warning(f"[GENERATE] Template missing on topic - topic_id={topic_id}")
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
                status="generating",  # 즉시 generating 상태
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

        # ✅ Task 예외 처리: 실패 시 로그 기록
        def handle_task_result(t: asyncio.Task):
            try:
                t.result()
            except asyncio.CancelledError:
                logger.warning(f"[BACKGROUND] Task cancelled - topic_id={topic_id}")
            except Exception as e:
                logger.error(f"[BACKGROUND] Task failed with unhandled exception - topic_id={topic_id}, error={str(e)}", exc_info=True)

        task.add_done_callback(handle_task_result)

        elapsed = time.time() - start_time
        logger.info(f"[GENERATE] Task created - topic_id={topic_id}, artifact_id={artifact.id}, elapsed={elapsed:.2f}s")

        response_dict = success_response(
            GenerateResponse(
                topic_id=topic_id,
                status="generating",
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
        # Topic 조회 및 권한 확인
        topic = await asyncio.to_thread(TopicDB.get_topic_by_id, topic_id)
        if not topic:
            logger.warning(f"[STATUS] Topic not found - topic_id={topic_id}")
            return error_response(
                code=ErrorCode.TOPIC_NOT_FOUND,
                http_status=404,
                message="토픽을 찾을 수 없습니다."
            )

        if topic.user_id != current_user.id and not current_user.is_admin:
            logger.warning(f"[STATUS] Unauthorized - topic_id={topic_id}, owner={topic.user_id}, requester={current_user.id}")
            return error_response(
                code=ErrorCode.TOPIC_UNAUTHORIZED,
                http_status=403,
                message="이 토픽에 접근할 권한이 없습니다."
            )

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
    # Topic 조회 및 권한 확인
    topic = await asyncio.to_thread(TopicDB.get_topic_by_id, topic_id)
    if not topic:
        logger.warning(f"[STREAM] Topic not found - topic_id={topic_id}")
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="토픽을 찾을 수 없습니다."
        )

    if topic.user_id != current_user.id and not current_user.is_admin:
        logger.warning(f"[STREAM] Unauthorized - topic_id={topic_id}, owner={topic.user_id}, requester={current_user.id}")
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 토픽에 접근할 권한이 없습니다."
        )

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
                        "event": "status_update" if artifact.status == "generating" else "completion",
                        "artifact_id": artifact.id,
                        "status": artifact.status,
                        "progress_percent": artifact.progress_percent
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"

                    logger.debug(f"[STREAM] Event sent - topic_id={topic_id}, artifact_id={artifact.id}, event={event_data['event']}, progress={artifact.progress_percent}%")

                    last_artifact = artifact

                    # 완료 또는 실패 시 종료
                    if artifact.status in ["completed", "failed"]:
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

    # 토픽 유효성 확인
    topic = TopicDB.get_topic_by_id(topic_id)
    if not topic:
        logger.warning(
            "[PROMPT_OPTIMIZATION] Topic not found - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id
        )
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="토픽을 찾을 수 없습니다."
        )

    # 토픽 소유자 권한 확인 (관리자 예외 없이 소유자만 허용)
    if topic.user_id != current_user.id:
        logger.warning(
            "[PROMPT_OPTIMIZATION] Unauthorized - topic_id=%s, owner=%s, requester=%s",
            topic_id,
            topic.user_id,
            current_user.id
        )
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 토픽에 접근할 권한이 없습니다."
        )

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

    # 토픽 확인
    topic = TopicDB.get_topic_by_id(topic_id)
    if not topic:
        logger.warning(
            "[PROMPT_OPTIMIZATION] Topic not found on fetch - topic_id=%s, user_id=%s",
            topic_id,
            current_user.id
        )
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="토픽을 찾을 수 없습니다."
        )

    # 권한 확인
    if topic.user_id != current_user.id:
        logger.warning(
            "[PROMPT_OPTIMIZATION] Unauthorized fetch - topic_id=%s, owner=%s, requester=%s",
            topic_id,
            topic.user_id,
            current_user.id
        )
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 토픽에 접근할 권한이 없습니다."
        )

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
        template_id: 템플릿 ID (필수, 누락 시 실패)
        user_id: 사용자 ID
        is_web_search: Claude 웹 검색 활성화 여부
    """
    if not template_id:
        raise InvalidTemplateError(
            code=ErrorCode.TEMPLATE_NOT_FOUND,
            http_status=404,
            message="템플릿 정보가 지정되지 않은 토픽입니다.",
            hint="/api/topics/plan 호출 후 템플릿이 지정된 토픽을 사용해주세요."
        )

    try:
        logger.info(f"[BACKGROUND] Report generation started - topic_id={topic_id}, artifact_id={artifact_id}")

        # === Step 1: 진행 상태 업데이트 ===
        logger.info(f"[BACKGROUND] Preparing content - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status="generating",
            progress_percent=10
        )

        # === Step 2: Claude API 호출 (non-blocking) ===
        logger.info(f"[BACKGROUND] Calling Claude API - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status="generating",
            progress_percent=20
        )

        claude = ClaudeClient()

        # User prompt 구성
        user_prompt = f"주제: {topic}\n\n계획:\n{plan}\n\n위의 계획을 바탕으로 상세한 보고서를 작성해주세요."

        optimized_system_prompt: Optional[str] = None

        # 프롬프트 고도화 결과를 조회하여 Claude system prompt를 최적화
        try:
            latest_optimization = await asyncio.to_thread(
                PromptOptimizationDB.get_latest_by_topic,
                topic_id
            )
            optimization_response = _build_prompt_optimization_response(latest_optimization)

            if optimization_response:
                optimization_payload = map_optimized_to_claude_payload(
                    optimization_response,
                    user_prompt,
                    PROMPT_OPTIMIZATION_DEFAULT_MODEL
                )
                optimized_system_prompt = optimization_payload.get("system")
                logger.info("[BACKGROUND] Optimization result found - using optimized prompts")
        except Exception as opt_exc:
            logger.error(
                "[BACKGROUND] Optimization lookup failed - topic_id=%s, error=%s",
                topic_id,
                str(opt_exc),
                exc_info=True
            )

        if optimized_system_prompt:
            system_prompt = optimized_system_prompt
        else:
            logger.info("[BACKGROUND] No optimization result - using default system prompt")
            system_prompt = await asyncio.to_thread(
                get_system_prompt,
                template_id=template_id,
                user_id=int(user_id) if isinstance(user_id, str) else user_id
            )

        start_time = time.time()
        # ✅ Non-blocking: Claude API 호출을 스레드 끝에서 실행
        markdown = await asyncio.to_thread(
            claude.generate_report,
            topic=topic,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            isWebSearch=is_web_search
        )
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = claude.last_input_tokens
        output_tokens = claude.last_output_tokens

        logger.info(f"[BACKGROUND] Content generated - topic_id={topic_id}, tokens={input_tokens}+{output_tokens}")

        # === Step 3: 마크다운 파싱 및 변환 ===
        logger.info(f"[BACKGROUND] Parsing markdown - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status="generating",
            progress_percent=50
        )

        # ✅ Non-blocking: 파싱을 스레드 끝에서 실행
        parsed_content = await asyncio.to_thread(
            parse_markdown_to_content,
            markdown
        )
        built_markdown = await asyncio.to_thread(
            build_report_md,
            parsed_content
        )

        # === Step 4: MD 파일 저장 ===
        logger.info(f"[BACKGROUND] Saving MD file - topic_id={topic_id}")
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status="generating",
            progress_percent=70
        )

        # ✅ Non-blocking: DB 조회를 스레드 끝에서 실행
        topic_obj = await asyncio.to_thread(
            TopicDB.get_topic_by_id,
            topic_id
        )
        version = next_artifact_version(topic_id, ArtifactKind.MD, topic_obj.language)
        base_dir, md_path = build_artifact_paths(topic_id, version, "report.md")

        # ✅ Non-blocking: 파일 I/O를 스레드 끝에서 실행
        bytes_written = await asyncio.to_thread(
            write_text,
            md_path,
            built_markdown
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
            status="generating",
            progress_percent=85
        )

        # ✅ Non-blocking: 메시지 생성을 스레드 끝에서 실행
        logger.info(f"[BACKGROUND] Saving to database Message - topic_id={topic_id}")
        assistant_msg = await asyncio.to_thread(
            MessageDB.create_message,
            topic_id,
            MessageCreate(role=MessageRole.ASSISTANT, content=built_markdown)
        )

        # ✅ Step 6: Artifact 상태 업데이트 + 파일 정보 추가 (완료)
        logger.info(f"[BACKGROUND] Updating artifact - topic_id={topic_id}, artifact_id={artifact_id}")
        completed_at = datetime.utcnow().isoformat()
        
        await asyncio.to_thread(
            ArtifactDB.update_artifact_status,
            artifact_id=artifact_id,
            status="completed",
            progress_percent=100,
            message_id=assistant_msg.id,
            file_path=str(md_path),  # ✅ MD 파일 경로 저장
            file_size=bytes_written,
            sha256=file_hash,
            completed_at=completed_at
        )

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
                status="failed",
                error_message=str(e),
                completed_at=datetime.utcnow().isoformat()
            )
        except Exception as db_error:
            logger.error(f"[BACKGROUND] Failed to update artifact status - error={str(db_error)}")
