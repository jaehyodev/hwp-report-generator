"""
Topic management API router.

Handles CRUD operations for topics (conversation threads).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import asyncio
import json
import time
import logging
from datetime import datetime

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
from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.database.ai_usage_db import AiUsageDB
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topics", tags=["Topics"])


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

    # === 5단계: System Prompt 선택 (우선순위: template > default) ===
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
    # TODO: is report 판별 로직 개선 필요
    try:
        #is_report = is_report_content(response_text)
        is_report = True  # 항상 보고서로 간주 임시 
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
        logger.info(f"[PLAN] Started - topic='{request.topic}', template_id={request.template_id}, user_id={current_user.id}")

        # Sequential Planning 호출
        plan_result = await sequential_planning(
            topic=request.topic,
            template_id=request.template_id,
            user_id=current_user.id,
            is_web_search=request.is_web_search
        )

        # 새로운 topic 생성 또는 기존 topic 조회
        topic_data = TopicCreate(
            input_prompt=request.topic,
            template_id=request.template_id
        )
        topic = TopicDB.create_topic(current_user.id, topic_data)

        elapsed = time.time() - start_time
        logger.info(f"[PLAN] Completed - topic_id={topic.id}, elapsed={elapsed:.2f}s")

        return success_response(
            PlanResponse(
                topic_id=topic.id,
                plan=plan_result["plan"],
            )
        )

    #TODO: 해당 오류 상황 발생시 다음과 같은 오류 발생 (AttributeError: type object 'ErrorCode' has no attribute 'REQUEST_TIMEOUT')
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
                status="scheduled",  # ✅ Scheduled state
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

        # System prompt 선택
        system_prompt = await asyncio.to_thread(
            get_system_prompt,
            template_id=template_id,
            user_id=int(user_id) if isinstance(user_id, str) else user_id
        )

        # User prompt 구성
        user_prompt = f"주제: {topic}\n\n계획:\n{plan}\n\n위의 계획을 바탕으로 상세한 보고서를 작성해주세요."

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
