"""Template management API router.

Handles template upload, retrieval, and deletion operations.
"""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import List

logger = logging.getLogger(__name__)

from app.models.user import User
from app.models.template import (
    UploadTemplateResponse,
    TemplateListResponse,
    TemplateDetailResponse,
    AdminTemplateResponse,
    PlaceholderResponse,
    UpdatePromptSystemRequest,
    UpdatePromptUserRequest,
    UpdatePromptResponse,
    RegeneratePromptResponse,
)
from app.database.template_db import TemplateDB, PlaceholderDB
from app.database.user_db import UserDB
from app.models.template import TemplateCreate
from app.utils.auth import get_current_active_user
from app.utils.response_helper import success_response, error_response, ErrorCode
from app.utils.templates_manager import TemplatesManager
from app.utils.prompts import (
    create_template_specific_rules,
    get_base_report_prompt,
    get_prompt_user_default,
)
from app.utils.meta_info_generator import generate_placeholder_metadata

router = APIRouter(prefix="/api/templates", tags=["Templates"])


@router.get("/admin/templates", summary="List all templates (admin only)")
async def admin_list_templates(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """모든 사용자의 템플릿을 조회합니다 (관리자 전용).

    반환(Returns):
        전체 템플릿 목록 (사용자명 포함)

    에러 코드(Error Codes):
        - AUTH.UNAUTHORIZED: 관리자 권한 없음

    예시(Examples):
        요청(Request): GET /api/admin/templates

        응답(Response, 200):
        ```json
        {
          "success": true,
          "data": [
            {
              "id": 1,
              "title": "재무보고서 템플릿",
              "username": "user1",
              "file_size": 45678,
              "placeholder_count": 5,
              "created_at": "2025-11-06T10:30:00"
            },
            ...
          ],
          "error": null,
          "meta": {"requestId": "uuid"}
        }
        ```
    """
    try:
        # 관리자 권한 검증
        if not current_user.is_admin:
            return error_response(
                code=ErrorCode.AUTH_UNAUTHORIZED,
                http_status=403,
                message="관리자 권한이 필요합니다.",
                hint="관리자에게 문의해주세요."
            )

        # 모든 템플릿 조회
        templates = TemplateDB.list_all_templates()
        response_data = []

        for template in templates:
            # 사용자 정보 조회
            user = UserDB.get_user_by_id(template.user_id)
            username = user.username if user else "Unknown"

            # 플레이스홀더 개수 조회
            placeholders = PlaceholderDB.get_placeholders_by_template(template.id)
            placeholder_count = len(placeholders)

            response_data.append(
                AdminTemplateResponse(
                    id=template.id,
                    title=template.title,
                    username=username,
                    file_size=template.file_size,
                    placeholder_count=placeholder_count,
                    created_at=template.created_at
                )
            )

        return success_response(response_data)
    except Exception as e:
        print(f"Error in admin_list_templates: {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="템플릿 목록 조회 중 오류가 발생했습니다."
        )


@router.post("", summary="Upload new template", status_code=201)
async def upload_template(
    file: UploadFile = File(...),
    title: str = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    """사용자가 커스텀 HWPX 템플릿을 업로드합니다.

    요청(Request):
        - file: HWPX 파일 (multipart/form-data)
        - title: 템플릿 제목 (string)

    반환(Returns):
        업로드된 템플릿 메타데이터와 플레이스홀더 목록

    에러 코드(Error Codes):
        - VALIDATION.INVALID_FORMAT: .hwpx 파일만 업로드 가능
        - TEMPLATE.INVALID_FORMAT: HWPX 파일이 손상됨
        - TEMPLATE.DUPLICATE_PLACEHOLDER: 플레이스홀더 중복
        - SERVER.INTERNAL_ERROR: 서버 오류

    예시(Examples):
        요청(Request):
        ```
        POST /api/templates
        Content-Type: multipart/form-data

        file: [binary HWPX file]
        title: "재무보고서 템플릿"
        ```

        응답(Response, 201):
        ```json
        {
          "success": true,
          "data": {
            "id": 1,
            "title": "재무보고서 템플릿",
            "filename": "template_20251106_123456.hwpx",
            "file_size": 45678,
            "placeholders": [
              {"key": "{{TITLE}}"},
              {"key": "{{SUMMARY}}"}
            ],
            "created_at": "2025-11-06T10:30:00"
          },
          "error": null,
          "meta": {"requestId": "uuid"}
        }
        ```
    """
    try:
        manager = TemplatesManager()

        # 1. 파일 확장자 검증
        if not file.filename.lower().endswith('.hwpx'):
            return error_response(
                code=ErrorCode.VALIDATION_INVALID_FORMAT,
                http_status=400,
                message=".hwpx 파일만 업로드 가능합니다.",
                hint="파일 형식을 확인해주세요."
            )

        # 2. 파일 내용 읽기
        file_content = await file.read()
        if not file_content:
            return error_response(
                code=ErrorCode.VALIDATION_INVALID_FORMAT,
                http_status=400,
                message="파일이 비어있습니다.",
                hint="유효한 HWPX 파일을 업로드해주세요."
            )

        # 3. HWPX 파일 검증 (Magic Byte)
        if not manager.validate_hwpx(file_content):
            return error_response(
                code=ErrorCode.TEMPLATE_INVALID_FORMAT,
                http_status=400,
                message="HWPX 파일이 손상되었습니다.",
                hint="파일을 다시 저장하거나 다른 파일을 시도해주세요."
            )

        # 4. 임시 파일 저장
        temp_filename = f"upload_{uuid.uuid4().hex}.hwpx"
        temp_file_path = manager.temp_dir / temp_filename
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)

        try:
            # 5. HWPX 압축 해제
            work_dir = manager.extract_hwpx(str(temp_file_path))

            try:
                # 6. 플레이스홀더 추출
                placeholders = manager.extract_placeholders(work_dir)
                # TODO: 정렬 필요 여부 검토 필요.
                # placeholder_list = sorted(placeholders)
                placeholder_list = placeholders

                # 7. 플레이스홀더 중복 검증
                if manager.has_duplicate_placeholders(placeholder_list):
                    duplicate_keys = manager.get_duplicate_placeholders(placeholder_list)
                    return error_response(
                        code=ErrorCode.TEMPLATE_DUPLICATE_PLACEHOLDER,
                        http_status=400,
                        message=f"플레이스홀더 {duplicate_keys[0]}이 중복되었습니다.",
                        details={"duplicate_keys": duplicate_keys},
                        hint="템플릿에서 중복된 플레이스홀더를 제거해주세요."
                    )

                # 8. SHA256 계산
                sha256 = manager.calculate_sha256(str(temp_file_path))

                # [신규] 9단계: Placeholder 메타정보 생성 (Claude API 기반)
                logger.info(f"[UPLOAD_TEMPLATE] Generating placeholder metadata with Claude - count={len(placeholder_list)}")
                from app.utils.meta_info_generator import generate_placeholder_metadata_with_claude
                try:
                    metadata = await generate_placeholder_metadata_with_claude(
                        raw_placeholders=placeholder_list,
                        template_context=title,
                        enable_fallback=True
                    )
                    logger.info(f"[UPLOAD_TEMPLATE] Metadata generated successfully - count={metadata.total_count}")
                except Exception as e:
                    logger.warning(f"[UPLOAD_TEMPLATE] Claude API failed, using fallback: {str(e)[:100]}")
                    # 폴백: 기본 규칙 기반 메타정보 생성
                    from app.utils.meta_info_generator import generate_placeholder_metadata
                    metadata = generate_placeholder_metadata(placeholder_list)

                # [개선] 10단계: BASE/규칙 분리 저장
                base_prompt = get_prompt_user_default()
                metadata_dicts = [
                    {**p.model_dump(), "key": p.placeholder_key}
                    for p in metadata.placeholders
                ] if metadata else None
                template_rules = create_template_specific_rules(placeholder_list, metadata_dicts)
                logger.info(
                    f"[UPLOAD_TEMPLATE] Template prompts prepared - base_length={len(base_prompt)}, "
                    f"rules_length={len(template_rules)}"
                )

                # [신규] 11단계: DB 트랜잭션으로 Template + Placeholders 원자적 저장
                template_data = TemplateCreate(
                    title=title,
                    description=None,
                    filename=file.filename,
                    file_path="",  # 임시값, 아래에서 업데이트
                    file_size=len(file_content),
                    sha256=sha256,
                    prompt_user=base_prompt,
                    prompt_system=template_rules
                )

                # create_template_with_transaction: Template + Placeholder 원자적 저장
                template = TemplateDB.create_template_with_transaction(
                    current_user.id,
                    template_data,
                    placeholder_list
                )

                # [기존] 12단계: 최종 파일 저장 경로로 이동
                final_file_path = manager.save_template_file(
                    str(temp_file_path),
                    current_user.id,
                    template.id
                )

                # [기존] 13단계: 응답 생성
                placeholder_responses = [
                    PlaceholderResponse(key=key)
                    for key in placeholder_list
                ]

                response_data = UploadTemplateResponse(
                    id=template.id,
                    title=template.title,
                    filename=template.filename,
                    file_size=template.file_size,
                    placeholders=placeholder_responses,
                    prompt_user=template.prompt_user,         # 신규
                    prompt_system=template.prompt_system,     # 신규
                    created_at=template.created_at
                )

                # 응답에 metadata 추가 (메타정보 JSON)
                response_dict = response_data.model_dump()
                if metadata:
                    response_dict['placeholders_metadata'] = metadata.model_dump()
                else:
                    response_dict['placeholders_metadata'] = None

                return success_response(response_dict)

            finally:
                # 임시 파일 정리
                manager.cleanup_temp_files(work_dir)

        except Exception as e:
            # 압축 해제 실패 시 임시 파일 정리
            if temp_file_path.exists():
                temp_file_path.unlink()
            raise e

    except Exception as e:
        # 최종 오류 처리
        print(f"Error in upload_template: {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="템플릿 업로드 중 오류가 발생했습니다.",
            hint="관리자에게 문의해주세요."
        )


@router.get("", summary="List user's templates")
async def list_templates(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """사용자의 템플릿 목록을 조회합니다.

    반환(Returns):
        사용자 소유 템플릿 목록

    예시(Examples):
        요청(Request): GET /api/templates

        응답(Response, 200):
        ```json
        {
          "success": true,
          "data": [
            {
              "id": 1,
              "title": "재무보고서 템플릿",
              "filename": "template_20251106_123456.hwpx",
              "file_size": 45678,
              "created_at": "2025-11-06T10:30:00"
            },
            {
              "id": 2,
              "title": "영업보고서 템플릿",
              "filename": "template_20251105_234567.hwpx",
              "file_size": 52341,
              "created_at": "2025-11-05T14:15:00"
            }
          ],
          "error": null,
          "meta": {"requestId": "uuid"}
        }
        ```
    """
    try:
        templates = TemplateDB.list_templates_by_user(current_user.id)
        response_data = [
            TemplateListResponse(
                id=t.id,
                title=t.title,
                filename=t.filename,
                file_size=t.file_size,
                created_at=t.created_at
            )
            for t in templates
        ]
        return success_response(response_data)
    except Exception as e:
        print(f"Error in list_templates: {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="템플릿 목록 조회 중 오류가 발생했습니다."
        )


@router.get("/{template_id}", summary="Get template details")
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """템플릿 상세 정보를 조회합니다 (메타데이터 + 플레이스홀더).

    경로 파라미터(Path Parameters):
        - template_id: 조회할 템플릿 ID

    반환(Returns):
        템플릿 메타데이터와 플레이스홀더 목록

    에러 코드(Error Codes):
        - TEMPLATE.NOT_FOUND: 템플릿을 찾을 수 없음
        - TEMPLATE.UNAUTHORIZED: 접근 권한 없음

    예시(Examples):
        요청(Request): GET /api/templates/1

        응답(Response, 200):
        ```json
        {
          "success": true,
          "data": {
            "id": 1,
            "title": "재무보고서 템플릿",
            "filename": "template_20251106_123456.hwpx",
            "file_size": 45678,
            "placeholders": [
              {"key": "{{TITLE}}"},
              {"key": "{{SUMMARY}}"},
              {"key": "{{BACKGROUND}}"},
              {"key": "{{MAIN_CONTENT}}"},
              {"key": "{{CONCLUSION}}"}
            ],
            "created_at": "2025-11-06T10:30:00"
          },
          "error": null,
          "meta": {"requestId": "uuid"}
        }
        ```
    """
    try:
        # 템플릿 조회 (권한 검증 포함)
        template = TemplateDB.get_template_by_id(template_id, current_user.id)

        if not template:
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="템플릿을 찾을 수 없습니다.",
                hint="템플릿 ID를 확인해주세요."
            )

        # 플레이스홀더 조회
        placeholders = PlaceholderDB.get_placeholders_by_template(template.id)
        placeholder_responses = [
            PlaceholderResponse(key=p.placeholder_key)
            for p in placeholders
        ]

        response_data = TemplateDetailResponse(
            id=template.id,
            title=template.title,
            filename=template.filename,
            file_size=template.file_size,
            placeholders=placeholder_responses,
            prompt_system=template.prompt_system,
            prompt_user=template.prompt_user,
            created_at=template.created_at
        )

        return success_response(response_data)
    except Exception as e:
        print(f"Error in get_template: {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="템플릿 조회 중 오류가 발생했습니다."
        )


@router.delete("/{template_id}", summary="Delete template")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """템플릿을 삭제합니다 (소프트 삭제).

    경로 파라미터(Path Parameters):
        - template_id: 삭제할 템플릿 ID

    반환(Returns):
        삭제 결과 메시지

    에러 코드(Error Codes):
        - TEMPLATE.NOT_FOUND: 템플릿을 찾을 수 없음
        - TEMPLATE.UNAUTHORIZED: 접근 권한 없음

    예시(Examples):
        요청(Request): DELETE /api/templates/1

        응답(Response, 200):
        ```json
        {
          "success": true,
          "data": {
            "id": 1,
            "message": "템플릿이 삭제되었습니다."
          },
          "error": null,
          "meta": {"requestId": "uuid"}
        }
        ```
    """
    try:
        # 권한 검증
        template = TemplateDB.get_template_by_id(template_id, current_user.id)
        if not template:
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="템플릿을 찾을 수 없습니다."
            )

        # 삭제 (soft delete)
        success = TemplateDB.delete_template(template_id, current_user.id)
        if not success:
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="템플릿을 찾을 수 없습니다."
            )

        return success_response({
            "id": template_id,
            "message": "템플릿이 삭제되었습니다."
        })
    except Exception as e:
        print(f"Error in delete_template: {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="템플릿 삭제 중 오류가 발생했습니다."
        )


@router.put("/{template_id}/prompt-system", summary="Update template prompt_system")
async def update_template_prompt_system(
    template_id: int,
    request: UpdatePromptSystemRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """템플릿의 prompt_system을 수정합니다.

    경로 파라미터(Path Parameters):
        - template_id: 수정할 템플릿 ID

    요청 본문(Request Body):
        - prompt_system: 새로운 시스템 프롬프트 (필수, 빈 값 불가)

    반환(Returns):
        수정된 템플릿 정보 (id, title, prompt_system, prompt_user, updated_at)

    에러 코드(Error Codes):
        - TEMPLATE.INVALID_PROMPT: prompt_system이 빈 값
        - TEMPLATE.NOT_FOUND: 템플릿을 찾을 수 없음
        - TEMPLATE.FORBIDDEN: 권한 부족 (자신의 템플릿이 아님)
        - AUTH.UNAUTHORIZED: 토큰 인증 실패
        - SERVER.INTERNAL_ERROR: 서버 오류

    권한 검증(Permission):
        - 일반 사용자: 자신이 생성한 템플릿만 수정 가능
        - 관리자(is_admin=True): 모든 사용자의 템플릿 수정 가능

    예시(Examples):
        요청(Request):
        ```
        PUT /api/templates/1/prompt-system
        Content-Type: application/json

        {
          "prompt_system": "새로운 시스템 프롬프트"
        }
        ```

        응답(Response, 200):
        ```json
        {
          "success": true,
          "message": "System prompt updated successfully",
          "data": {
            "id": 1,
            "title": "재무보고서 템플릿",
            "prompt_system": "새로운 시스템 프롬프트",
            "prompt_user": "기존 사용자 프롬프트",
            "updated_at": "2025-11-11T10:30:00"
          }
        }
        ```
    """
    try:
        # 1. 입력값 검증
        if not request.prompt_system or request.prompt_system.strip() == "":
            logger.warning(f"[UPDATE_PROMPT_SYSTEM] Empty prompt_system - user_id={current_user.id}")
            return error_response(
                code=ErrorCode.TEMPLATE_INVALID_PROMPT,
                http_status=400,
                message="System prompt cannot be empty",
                hint="유효한 시스템 프롬프트를 입력해주세요."
            )

        # 2. 템플릿 조회 및 권한 검증
        template = TemplateDB.get_template_by_id(template_id)
        if not template:
            logger.warning(f"[UPDATE_PROMPT_SYSTEM] Template not found - template_id={template_id}")
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="Template not found",
                hint="템플릿 ID를 확인해주세요."
            )

        # 3. 권한 검증 (관리자 또는 소유자만 가능)
        if not current_user.is_admin and template.user_id != current_user.id:
            logger.warning(
                f"[UPDATE_PROMPT_SYSTEM] Permission denied - user_id={current_user.id}, "
                f"template_owner_id={template.user_id}"
            )
            return error_response(
                code=ErrorCode.TEMPLATE_FORBIDDEN,
                http_status=403,
                message="Forbidden: Cannot modify other user's template",
                hint="자신이 생성한 템플릿만 수정할 수 있습니다."
            )

        # 4. DB 업데이트
        updated_template = TemplateDB.update_prompt_system(template_id, request.prompt_system)
        if not updated_template:
            logger.error(f"[UPDATE_PROMPT_SYSTEM] DB update failed - template_id={template_id}")
            return error_response(
                code=ErrorCode.SERVER_INTERNAL_ERROR,
                http_status=500,
                message="Failed to update prompt_system"
            )

        # 5. 응답 생성
        logger.info(f"[UPDATE_PROMPT_SYSTEM] Success - template_id={template_id}, user_id={current_user.id}")
        response_data = UpdatePromptResponse(
            id=updated_template.id,
            title=updated_template.title,
            prompt_system=updated_template.prompt_system,
            prompt_user=updated_template.prompt_user,
            updated_at=updated_template.updated_at
        )
        return success_response(response_data)

    except Exception as e:
        logger.error(f"[UPDATE_PROMPT_SYSTEM] Error - {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="Failed to update system prompt"
        )


@router.put("/{template_id}/prompt-user", summary="Update template prompt_user")
async def update_template_prompt_user(
    template_id: int,
    request: UpdatePromptUserRequest,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """템플릿의 prompt_user를 수정합니다.

    경로 파라미터(Path Parameters):
        - template_id: 수정할 템플릿 ID

    요청 본문(Request Body):
        - prompt_user: 새로운 사용자 프롬프트 (선택사항, 빈 값 가능)

    반환(Returns):
        수정된 템플릿 정보 (id, title, prompt_system, prompt_user, updated_at)

    에러 코드(Error Codes):
        - TEMPLATE.NOT_FOUND: 템플릿을 찾을 수 없음
        - TEMPLATE.FORBIDDEN: 권한 부족 (자신의 템플릿이 아님)
        - AUTH.UNAUTHORIZED: 토큰 인증 실패
        - SERVER.INTERNAL_ERROR: 서버 오류

    권한 검증(Permission):
        - 일반 사용자: 자신이 생성한 템플릿만 수정 가능
        - 관리자(is_admin=True): 모든 사용자의 템플릿 수정 가능

    예시(Examples):
        요청(Request):
        ```
        PUT /api/templates/1/prompt-user
        Content-Type: application/json

        {
          "prompt_user": "새로운 사용자 프롬프트"
        }
        ```

        응답(Response, 200):
        ```json
        {
          "success": true,
          "message": "User prompt updated successfully",
          "data": {
            "id": 1,
            "title": "재무보고서 템플릿",
            "prompt_system": "기존 시스템 프롬프트",
            "prompt_user": "새로운 사용자 프롬프트",
            "updated_at": "2025-11-11T10:30:00"
          }
        }
        ```
    """
    try:
        # 1. 템플릿 조회 및 권한 검증
        template = TemplateDB.get_template_by_id(template_id)
        if not template:
            logger.warning(f"[UPDATE_PROMPT_USER] Template not found - template_id={template_id}")
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="Template not found",
                hint="템플릿 ID를 확인해주세요."
            )

        # 2. 권한 검증 (관리자 또는 소유자만 가능)
        if not current_user.is_admin and template.user_id != current_user.id:
            logger.warning(
                f"[UPDATE_PROMPT_USER] Permission denied - user_id={current_user.id}, "
                f"template_owner_id={template.user_id}"
            )
            return error_response(
                code=ErrorCode.TEMPLATE_FORBIDDEN,
                http_status=403,
                message="Forbidden: Cannot modify other user's template",
                hint="자신이 생성한 템플릿만 수정할 수 있습니다."
            )

        # 3. DB 업데이트
        updated_template = TemplateDB.update_prompt_user(template_id, request.prompt_user)
        if not updated_template:
            logger.error(f"[UPDATE_PROMPT_USER] DB update failed - template_id={template_id}")
            return error_response(
                code=ErrorCode.SERVER_INTERNAL_ERROR,
                http_status=500,
                message="Failed to update prompt_user"
            )

        # 4. 응답 생성
        logger.info(f"[UPDATE_PROMPT_USER] Success - template_id={template_id}, user_id={current_user.id}")
        response_data = UpdatePromptResponse(
            id=updated_template.id,
            title=updated_template.title,
            prompt_system=updated_template.prompt_system,
            prompt_user=updated_template.prompt_user,
            updated_at=updated_template.updated_at
        )
        return success_response(response_data)

    except Exception as e:
        logger.error(f"[UPDATE_PROMPT_USER] Error - {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="Failed to update user prompt"
        )


@router.post("/{template_id}/regenerate-prompt-system", summary="Regenerate template prompt_system")
async def regenerate_template_prompt_system(
    template_id: int,
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """템플릿의 prompt_system을 재생성합니다.

    경로 파라미터(Path Parameters):
        - template_id: 재생성할 템플릿 ID

    반환(Returns):
        재생성된 템플릿 정보 (id, prompt_system, regenerated_at)

    에러 코드(Error Codes):
        - TEMPLATE.NOT_FOUND: 템플릿을 찾을 수 없음
        - TEMPLATE.FORBIDDEN: 권한 부족 (자신의 템플릿이 아님)
        - TEMPLATE.GENERATION_FAILED: Claude API 호출 실패
        - AUTH.UNAUTHORIZED: 토큰 인증 실패
        - SERVER.INTERNAL_ERROR: 서버 오류

    권한 검증(Permission):
        - 일반 사용자: 자신이 생성한 템플릿만 재생성 가능
        - 관리자(is_admin=True): 모든 사용자의 템플릿 재생성 가능

    재생성 로직:
        1. 템플릿에 연결된 Placeholder 목록 조회
        2. generate_placeholder_metadata()로 메타정보 생성 (Claude API)
        3. create_system_prompt_with_metadata()로 System Prompt 생성
        4. DB에 저장

    예시(Examples):
        요청(Request):
        ```
        POST /api/templates/1/regenerate-prompt-system
        ```

        응답(Response, 200):
        ```json
        {
          "success": true,
          "message": "System prompt regenerated successfully",
          "data": {
            "id": 1,
            "prompt_system": "Claude API로 재생성된 시스템 프롬프트",
            "regenerated_at": "2025-11-11T10:35:00"
          }
        }
        ```
    """
    try:
        # 1. 템플릿 조회 및 권한 검증
        template = TemplateDB.get_template_by_id(template_id)
        if not template:
            logger.warning(f"[REGENERATE_PROMPT] Template not found - template_id={template_id}")
            return error_response(
                code=ErrorCode.TEMPLATE_NOT_FOUND,
                http_status=404,
                message="Template not found",
                hint="템플릿 ID를 확인해주세요."
            )

        # 2. 권한 검증 (관리자 또는 소유자만 가능)
        if not current_user.is_admin and template.user_id != current_user.id:
            logger.warning(
                f"[REGENERATE_PROMPT] Permission denied - user_id={current_user.id}, "
                f"template_owner_id={template.user_id}"
            )
            return error_response(
                code=ErrorCode.TEMPLATE_FORBIDDEN,
                http_status=403,
                message="Forbidden: Cannot modify other user's template",
                hint="자신이 생성한 템플릿만 재생성할 수 있습니다."
            )

        # 3. 플레이스홀더 조회
        try:
            placeholders = PlaceholderDB.get_placeholders_by_template(template_id)
            placeholder_keys = [p.placeholder_key for p in placeholders]
            logger.info(
                f"[REGENERATE_PROMPT] Placeholders loaded - template_id={template_id}, "
                f"count={len(placeholder_keys)}"
            )
        except Exception as e:
            logger.error(f"[REGENERATE_PROMPT] Failed to fetch placeholders - {str(e)}", exc_info=True)
            return error_response(
                code=ErrorCode.TEMPLATE_GENERATION_FAILED,
                http_status=500,
                message="Failed to load placeholders for regeneration"
            )

        # 4. Claude API로 메타정보 생성 (선택사항)
        metadata_dicts = None
        if placeholder_keys:
            try:
                metadata = generate_placeholder_metadata(placeholder_keys)
                logger.info(
                    f"[REGENERATE_PROMPT] Metadata generated - template_id={template_id}, "
                    f"metadata_count={metadata.total_count if metadata else 0}"
                )
                # metadata를 dict 리스트로 변환
                # 동적 매핑: placeholder_key를 "key" 필드로 매핑하여 prompts.py와 호환
                metadata_dicts = [
                    {**p.model_dump(), "key": p.placeholder_key}
                    for p in metadata.placeholders
                ] if metadata else None
            except Exception as e:
                logger.warning(f"[REGENERATE_PROMPT] Metadata generation failed (non-blocking) - {str(e)}")
                # 메타정보 생성 실패는 비치명적 (metadata=None으로 계속 진행)

        # 5. 메타정보를 포함한 규칙(System Prompt) 생성
        try:
            new_prompt_system = create_template_specific_rules(placeholder_keys, metadata_dicts)
            logger.info(
                f"[REGENERATE_PROMPT] System prompt generated - template_id={template_id}, "
                f"prompt_length={len(new_prompt_system)}"
            )
        except Exception as e:
            logger.error(f"[REGENERATE_PROMPT] Failed to generate prompt - {str(e)}", exc_info=True)
            return error_response(
                code=ErrorCode.TEMPLATE_GENERATION_FAILED,
                http_status=500,
                message="Failed to regenerate system prompt"
            )

        # 6. DB 업데이트
        try:
            updated_template = TemplateDB.update_prompt_system(template_id, new_prompt_system)
            if not updated_template:
                logger.error(f"[REGENERATE_PROMPT] DB update failed - template_id={template_id}")
                return error_response(
                    code=ErrorCode.SERVER_INTERNAL_ERROR,
                    http_status=500,
                    message="Failed to save regenerated prompt"
                )
        except Exception as e:
            logger.error(f"[REGENERATE_PROMPT] DB error - {str(e)}")
            return error_response(
                code=ErrorCode.SERVER_INTERNAL_ERROR,
                http_status=500,
                message="Failed to save regenerated prompt"
            )

        # 7. 응답 생성
        logger.info(f"[REGENERATE_PROMPT] Success - template_id={template_id}, user_id={current_user.id}")
        response_data = RegeneratePromptResponse(
            id=updated_template.id,
            prompt_system=updated_template.prompt_system,
            regenerated_at=updated_template.updated_at
        )
        return success_response(response_data)

    except Exception as e:
        logger.error(f"[REGENERATE_PROMPT] Unexpected error - {str(e)}")
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="Failed to regenerate system prompt"
        )
