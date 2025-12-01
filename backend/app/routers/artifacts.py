"""
Artifact management API router.

Handles artifact retrieval, download, and conversion operations.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from typing import Optional
import os
import time
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from app.models.user import User
from app.models.artifact import ArtifactResponse, ArtifactListResponse, ArtifactContentResponse, ArtifactCreate
from app.models.convert_models import MdType
from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.utils.auth import get_current_active_user
from app.utils.response_helper import success_response, error_response, ErrorCode
from app.utils.hwp_handler import HWPHandler
from app.utils.markdown_parser import parse_markdown_to_content, parse_markdown_to_md_elements
from app.utils.md_to_hwpx_converter import convert_markdown_to_hwpx
from app.utils.file_utils import next_artifact_version, build_artifact_paths, sha256_of
from shared.types.enums import ArtifactKind
from shared.constants import ProjectPath

router = APIRouter(prefix="/api/artifacts", tags=["Artifacts"])


@router.get("/{artifact_id}", summary="Get artifact by ID")
async def get_artifact(
    artifact_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """지정된 ID로 아티팩트(artifact) 메타데이터를 조회합니다.

    경로 파라미터(Path Parameters):
        - artifact_id: 조회할 아티팩트의 고유 ID

    반환(Returns):
        ArtifactResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - ARTIFACT.NOT_FOUND: 해당 아티팩트를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 상위 주제(topic)에 대한 소유 권한이 없음

    예시(Examples):
        요청(Request): GET /api/artifacts/1

        응답(Response, 200):
        ```json
        {
        "success": true,
        "data": {
            "id": 1,
            "topic_id": 1,
            "message_id": 2,
            "kind": "md",
            "locale": "ko",
            "version": 1,
            "filename": "report_v1.md",
            "file_path": "artifacts/topics/1/messages/report_v1.md",
            "file_size": 2048,
            "created_at": "2025-10-28T10:30:20"
        },
        "error": null,
        "meta": {"requestId": "req_abc123"},
        "feedback": []
        }
        ```
    """

    artifact = ArtifactDB.get_artifact_by_id(artifact_id)
    if not artifact:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트를 찾을 수 없습니다."
        )

    # Check ownership
    topic = TopicDB.get_topic_by_id(artifact.topic_id)
    if not topic or (topic.user_id != current_user.id and not current_user.is_admin):
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 아티팩트에 접근할 권한이 없습니다."
        )

    return success_response(ArtifactResponse.model_validate(artifact))


@router.get("/{artifact_id}/content", summary="Get artifact content")
async def get_artifact_content(
    artifact_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """아티팩트 파일의 내용을 조회합니다. (MD 파일 전용)

    경로 파라미터(Path Parameters):
        - artifact_id: 조회할 아티팩트의 ID

    반환(Returns):
        ArtifactContentResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - ARTIFACT.NOT_FOUND: 해당 아티팩트를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 상위 주제(topic)에 대한 소유 권한이 없음
        - ARTIFACT.INVALID_KIND: MD 파일 이외의 형식은 텍스트로 읽을 수 없음

    참고(Note):
        이 엔드포인트는 MD 파일만 지원합니다.  
        HWPX 파일의 경우, 다운로드 전용 엔드포인트를 사용해야 합니다.

    예시(Examples):
        요청(Request): GET /api/artifacts/1/content

        응답(Response, 200):
        ```json
        {
        "success": true,
        "data": {
            "artifact_id": 1,
            "content": "# 디지털뱅킹 트렌드 분석 보고서\\n\\n## 요약\\n...",
            "filename": "report_v1.md",
            "kind": "md"
        },
        "error": null,
        "meta": {"requestId": "req_def456"},
        "feedback": []
        }
        ```
    """
    artifact = ArtifactDB.get_artifact_by_id(artifact_id)
    if not artifact:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트를 찾을 수 없습니다."
        )

    # Check ownership
    topic = TopicDB.get_topic_by_id(artifact.topic_id)
    if not topic or (topic.user_id != current_user.id and not current_user.is_admin):
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 아티팩트에 접근할 권한이 없습니다."
        )

    # Only support MD files for content reading
    if artifact.kind != ArtifactKind.MD:
        return error_response(
            code=ErrorCode.ARTIFACT_INVALID_KIND,
            http_status=400,
            message="MD 파일만 내용 조회가 가능합니다.",
            hint="HWPX 파일은 다운로드를 사용하세요."
        )

    try:
        # Read file content
        with open(artifact.file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = ArtifactContentResponse(
            artifact_id=artifact.id,
            content=content,
            filename=artifact.filename,
            kind=artifact.kind
        )

        return success_response(result)

    except FileNotFoundError:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트 파일을 찾을 수 없습니다.",
            details={"file_path": artifact.file_path}
        )
    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="아티팩트 내용 조회에 실패했습니다.",
            details={"error": str(e)}
        )


@router.get("/{artifact_id}/download", summary="Download artifact file")
async def download_artifact(
    artifact_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """아티팩트 파일을 다운로드합니다. (MD, HWPX 등 지원)

    경로 파라미터(Path Parameters):
        - artifact_id: 다운로드할 아티팩트의 ID

    반환(Returns):
        첨부 파일(File) 형태로 반환됩니다.

    에러 코드(Error Codes):
        - ARTIFACT.NOT_FOUND: 해당 아티팩트를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 상위 주제(topic)에 대한 소유 권한이 없음
        - ARTIFACT.DOWNLOAD_FAILED: 파일 다운로드에 실패함

    예시(Examples):
        요청(Request): GET /api/artifacts/2/download

        응답(Response, 200): Content-Disposition 헤더가 포함된 파일 다운로드 응답
    """

    artifact = ArtifactDB.get_artifact_by_id(artifact_id)
    if not artifact:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트를 찾을 수 없습니다."
        )

    # Check ownership
    topic = TopicDB.get_topic_by_id(artifact.topic_id)
    if not topic or (topic.user_id != current_user.id and not current_user.is_admin):
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 아티팩트를 다운로드할 권한이 없습니다."
        )

    # Check file exists
    if not os.path.exists(artifact.file_path):
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트 파일을 찾을 수 없습니다.",
            details={"file_path": artifact.file_path}
        )

    try:
        # Determine media type
        media_types = {
            ArtifactKind.MD: "text/markdown",
            ArtifactKind.HWPX: "application/x-hwpx",
            ArtifactKind.PDF: "application/pdf"
        }
        media_type = media_types.get(artifact.kind, "application/octet-stream")

        return FileResponse(
            path=artifact.file_path,
            filename=artifact.filename,
            media_type=media_type
        )

    except Exception as e:
        return error_response(
            code=ErrorCode.ARTIFACT_DOWNLOAD_FAILED,
            http_status=500,
            message="파일 다운로드에 실패했습니다.",
            details={"error": str(e)}
        )


@router.get("/messages/{message_id}/hwpx/download", summary="Download HWPX by message")
async def download_message_hwpx(
    message_id: int,
    locale: str = "ko",
    current_user: User = Depends(get_current_active_user)
):
    """지정된 메시지 ID에 대한 최신 HWPX 아티팩트를 다운로드하거나, 존재하지 않을 경우 새로 생성하여 다운로드합니다.

    기능(Flow):
        1. 메시지 및 상위 주제(topic)에 대한 접근 권한 검증
        2. 기존 HWPX 아티팩트 존재 시 해당 파일을 직접 반환
        3. 기존 HWPX가 없을 경우 MD 아티팩트를 기반으로 HWPX 파일을 새로 생성 후 반환

    경로 파라미터(Path Parameters):
        - message_id: 다운로드할 메시지의 ID

    쿼리 파라미터(Query Parameters):
        - locale: 언어 코드 (기본값: "ko")

    반환(Returns):
        - HWPX 파일을 첨부 파일 형태(FileResponse)로 반환

    에러 코드(Error Codes):
        - MESSAGE.NOT_FOUND: 메시지를 찾을 수 없음
        - TOPIC.NOT_FOUND: 주제를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 해당 주제에 대한 권한이 없음
        - ARTIFACT.NOT_FOUND: 아티팩트 파일을 찾을 수 없음
        - ARTIFACT.CONVERSION_FAILED: MD → HWPX 변환 중 오류 발생

    참고(Note):
        - 기존 HWPX 파일이 존재하지 않을 경우, 내부적으로 `HWPHandler`를 이용해 MD 내용을 기반으로 HWPX 파일을 생성합니다.
        - 생성된 HWPX 파일은 `artifacts/topics/{topic_id}/...` 경로에 저장되며, 이후 동일 메시지의 요청에서는 재생성 없이 바로 다운로드됩니다.

    예시(Examples):
        요청(Request):  
        GET /api/messages/12/hwpx/download?locale=ko

        응답(Response, 200):  
        Content-Disposition 헤더가 포함된 HWPX 파일 다운로드 응답
    """
    message = MessageDB.get_message_by_id(message_id)
    if not message:
        return error_response(
            code=ErrorCode.MESSAGE_NOT_FOUND,
            http_status=404,
            message="메시지를 찾을 수 없습니다."
        )

    topic = TopicDB.get_topic_by_id(message.topic_id)
    if not topic:
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="주제를 찾을 수 없습니다."
        )

    if topic.user_id != current_user.id and not current_user.is_admin:
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 리소스에 접근할 권한이 없습니다."
        )

    existing_hwpx = ArtifactDB.get_latest_artifact_by_message_and_kind(
        message_id,
        ArtifactKind.HWPX,
        locale
    )

    if existing_hwpx:
        if os.path.exists(existing_hwpx.file_path):
            return FileResponse(
                path=existing_hwpx.file_path,
                filename=existing_hwpx.filename,
                media_type="application/x-hwpx"
            )

        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트 파일을 찾을 수 없습니다.",
            details={"file_path": existing_hwpx.file_path}
        )
    # 기존에 작성된 MD 파일 조회
    md_artifact = ArtifactDB.get_latest_artifact_by_message_and_kind(
        message_id,
        ArtifactKind.MD,
        locale
    )

    if not md_artifact:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="해당 메시지의 MD 아티팩트를 찾을 수 없습니다."
        )

    if not os.path.exists(md_artifact.file_path):
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트 파일을 찾을 수 없습니다.",
            details={"file_path": md_artifact.file_path}
        )

    try:
        with open(md_artifact.file_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        content = parse_markdown_to_content(md_text)

        template_path = ProjectPath.BACKEND / "templates" / "report_template.hwpx"
        if not template_path.exists():
            return error_response(
                code=ErrorCode.ARTIFACT_CONVERSION_FAILED,
                http_status=500,
                message="HWPX 템플릿 파일을 찾을 수 없습니다.",
                details={"template_path": str(template_path)}
            )

        temp_dir = ProjectPath.BACKEND / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        hwp_handler = HWPHandler(
            template_path=str(template_path),
            temp_dir=str(temp_dir),
            output_dir=str(temp_dir)
        )

        temp_hwpx_filename = f"temp_{message_id}_{int(time.time())}.hwpx"
        temp_hwpx_path = hwp_handler.generate_report(content, temp_hwpx_filename)

        version = next_artifact_version(topic.id, ArtifactKind.HWPX, locale)
        md_stem = Path(md_artifact.filename).stem or f"report_{message_id}"
        hwpx_filename = f"{md_stem}.hwpx"
        base_dir, hwpx_path = build_artifact_paths(topic.id, version, hwpx_filename)
        base_dir.mkdir(parents=True, exist_ok=True)

        shutil.move(temp_hwpx_path, hwpx_path)

        file_size = hwpx_path.stat().st_size
        file_hash = sha256_of(hwpx_path)

        hwpx_artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=message_id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.HWPX,
                locale=locale,
                version=version,
                filename=hwpx_path.name,
                file_path=str(hwpx_path),
                file_size=file_size,
                sha256=file_hash
            )
        )

        return FileResponse(
            path=hwpx_artifact.file_path,
            filename=hwpx_artifact.filename,
            media_type="application/x-hwpx"
        )

    except Exception as e:
        if 'temp_hwpx_path' in locals() and os.path.exists(temp_hwpx_path):
            os.remove(temp_hwpx_path)

        return error_response(
            code=ErrorCode.ARTIFACT_CONVERSION_FAILED,
            http_status=500,
            message="HWPX 변환 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.post("/{artifact_id}/convert-hwpx", summary="Convert Markdown artifact to HWPX")
async def convert_artifact_to_hwpx(
    artifact_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """Convert a Markdown artifact directly into an HWPX document."""

    artifact = ArtifactDB.get_artifact_by_id(artifact_id)
    if not artifact:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트를 찾을 수 없습니다."
        )

    topic = TopicDB.get_topic_by_id(artifact.topic_id)
    if not topic or (topic.user_id != current_user.id and not current_user.is_admin):
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 아티팩트에 접근할 권한이 없습니다."
        )

    if artifact.kind != ArtifactKind.MD:
        return error_response(
            code=ErrorCode.ARTIFACT_INVALID_KIND,
            http_status=400,
            message="MD 형식의 아티팩트만 변환할 수 있습니다.",
            details={"current_kind": artifact.kind.value}
        )

    # === JSON Artifact Validation (CRITICAL) ===
    # 같은 topic_id와 version을 가진 JSON artifact 검색
    logger.info(f"[CONVERT-HWPX] Validating JSON artifact - artifact_id={artifact_id}, topic_id={artifact.topic_id}, version={artifact.version}")

    json_artifacts, _ = ArtifactDB.get_artifacts_by_topic(artifact.topic_id)
    matching_json = [
        a for a in json_artifacts
        if a.kind == ArtifactKind.JSON and a.version == artifact.version
    ]

    if not matching_json:
        logger.warning(f"[CONVERT-HWPX] JSON artifact not found - artifact_id={artifact_id}, topic_id={artifact.topic_id}, version={artifact.version}")
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=400,
            message="JSON artifact가 없습니다.",
            hint="관리자에게 문의하세요."
        )

    json_artifact = matching_json[0]
    logger.info(f"[CONVERT-HWPX] JSON artifact found - json_artifact_id={json_artifact.id}")

    # JSON artifact 파일 존재 여부 검증
    json_artifact_path = Path(json_artifact.file_path)
    if not json_artifact_path.exists():
        logger.warning(f"[CONVERT-HWPX] JSON artifact file not found - path={json_artifact.file_path}")
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=400,
            message="JSON artifact 파일을 찾을 수 없습니다.",
            hint="관리자에게 문의하세요."
        )

    if not artifact.file_path:
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트 파일 경로가 지정되지 않았습니다."
        )

    artifact_path = Path(artifact.file_path)
    if not artifact_path.exists():
        return error_response(
            code=ErrorCode.ARTIFACT_NOT_FOUND,
            http_status=404,
            message="아티팩트 파일을 찾을 수 없습니다.",
            details={"file_path": artifact.file_path}
        )

    try:
        md_text = artifact_path.read_text(encoding="utf-8")
    except Exception as exc:
        return error_response(
            code=ErrorCode.ARTIFACT_CONVERSION_FAILED,
            http_status=400,
            message="마크다운 파일을 읽을 수 없습니다.",
            details={"error": str(exc)}
        )

    md_elements = parse_markdown_to_md_elements(md_text)
    convertible = [
        element for element in md_elements
        if element.type not in (MdType.TITLE, MdType.NO_CONVERT)
    ]
    if not convertible:
        return error_response(
            code=ErrorCode.ARTIFACT_CONVERSION_FAILED,
            http_status=400,
            message="변환 가능한 마크다운 요소가 없습니다."
        )

    version = next_artifact_version(topic.id, ArtifactKind.HWPX, artifact.locale)
    md_stem = Path(artifact.filename).stem or f"artifact_{artifact.id}"
    hwpx_filename = f"{md_stem}.hwpx"
    base_dir, hwpx_path = build_artifact_paths(topic.id, version, hwpx_filename)
    base_dir.mkdir(parents=True, exist_ok=True)

    try:
        convert_markdown_to_hwpx(md_elements, str(hwpx_path))
        file_size = hwpx_path.stat().st_size
    except FileNotFoundError as exc:
        if hwpx_path.exists():
            hwpx_path.unlink()
        return error_response(
            code=ErrorCode.TEMPLATE_NOT_FOUND,
            http_status=500,
            message="HWPX 템플릿 파일을 찾을 수 없습니다.",
            details={"error": str(exc)}
        )
    except Exception as exc:
        if hwpx_path.exists():
            hwpx_path.unlink()
        return error_response(
            code=ErrorCode.ARTIFACT_CONVERSION_FAILED,
            http_status=500,
            message="HWPX 변환 중 오류가 발생했습니다.",
            details={"error": str(exc)}
        )

    file_hash = sha256_of(hwpx_path)
    hwpx_artifact = ArtifactDB.create_artifact(
        topic_id=topic.id,
        message_id=artifact.message_id,
        artifact_data=ArtifactCreate(
            kind=ArtifactKind.HWPX,
            locale=artifact.locale,
            version=version,
            filename=hwpx_filename,
            file_path=str(hwpx_path),
            file_size=file_size,
            sha256=file_hash
        )
    )

    return FileResponse(
        path=hwpx_artifact.file_path,
        filename=hwpx_artifact.filename,
        media_type="application/x-hwpx"
    )


@router.get("/topics/{topic_id}", summary="Get artifacts by topic")
async def get_artifacts_by_topic(
    topic_id: int,
    kind: Optional[ArtifactKind] = None,
    locale: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_active_user)
):
    """주제(Topic)에 포함된 아티팩트 목록을 조회합니다.  
    필터 조건을 통해 특정 종류(kind)나 언어(locale)별로 조회할 수 있습니다.

    경로 파라미터(Path Parameters):
        - topic_id: 조회할 주제의 ID

    쿼리 파라미터(Query Parameters):
        - kind: 아티팩트 종류 필터 (md / hwpx / pdf) (선택)
        - locale: 언어 필터 (ko / en) (선택)
        - page: 페이지 번호 (기본값: 1)
        - page_size: 페이지당 항목 수 (기본값: 50, 최대: 100)

    반환(Returns):
        ArtifactListResponse 데이터를 포함한 표준 ApiResponse 객체를 반환합니다.

    에러 코드(Error Codes):
        - TOPIC.NOT_FOUND: 해당 주제를 찾을 수 없음
        - TOPIC.UNAUTHORIZED: 사용자가 해당 주제에 대한 소유 권한이 없음

    예시(Examples):
        요청(Request):  
        GET /api/artifacts/topics/1?kind=md&locale=ko&page=1&page_size=10

        응답(Response, 200):
        ```json
        {
        "success": true,
        "data": {
            "artifacts": [...],
            "total": 5,
            "topic_id": 1
        },
        "error": null,
        "meta": {"requestId": "req_ghi789"},
        "feedback": []
        }
        ```
"""

    # Check topic exists and user owns it
    topic = TopicDB.get_topic_by_id(topic_id)
    if not topic:
        return error_response(
            code=ErrorCode.TOPIC_NOT_FOUND,
            http_status=404,
            message="주제를 찾을 수 없습니다."
        )

    if topic.user_id != current_user.id and not current_user.is_admin:
        return error_response(
            code=ErrorCode.TOPIC_UNAUTHORIZED,
            http_status=403,
            message="이 주제의 아티팩트를 조회할 권한이 없습니다."
        )

    try:
        # Validate page_size
        if page_size > 100:
            page_size = 100

        offset = (page - 1) * page_size
        artifacts, total = ArtifactDB.get_artifacts_by_topic(
            topic_id=topic_id,
            kind=kind,
            locale=locale,
            limit=page_size,
            offset=offset
        )

        artifact_responses = [ArtifactResponse.model_validate(a) for a in artifacts]
        result = ArtifactListResponse(
            artifacts=artifact_responses,
            total=total,
            topic_id=topic_id
        )

        return success_response(result)

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_DATABASE_ERROR,
            http_status=500,
            message="아티팩트 목록 조회에 실패했습니다.",
            details={"error": str(e)}
        )
