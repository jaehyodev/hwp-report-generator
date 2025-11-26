"""
인증 관련 API 라우터
"""
from fastapi import APIRouter, Depends

from app.models.user import UserCreate, UserLogin, UserResponse, PasswordChange, UserUpdate
from app.database.user_db import UserDB
from app.utils.auth import (
    hash_password,
    verify_password,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_active_user
)
from app.utils.response_helper import success_response, error_response, ErrorCode

router = APIRouter(prefix="/api/auth", tags=["인증"])


@router.post("/register")
async def register(user_data: UserCreate):
    """회원가입 API.

    이메일, 사용자명, 비밀번호를 입력받아 회원가입.
    초기 상태는 is_active=False (관리자 승인 대기).

    Args:
        user_data: 회원가입 정보

    Returns:
        표준 API 응답 (성공 또는 에러)
    """
    try:
        # 이메일 중복 확인
        existing_user = UserDB.get_user_by_email(user_data.email)
        if existing_user:
            return error_response(
                code=ErrorCode.AUTH_DUPLICATE_EMAIL,
                http_status=400,
                message="이미 등록된 이메일입니다.",
                hint="다른 이메일 주소를 사용해주세요."
            )

        # 비밀번호 해싱
        hashed_password = hash_password(user_data.password)

        # 사용자 생성
        user = UserDB.create_user(user_data, hashed_password)

        return success_response({
            "message": "회원가입이 완료되었습니다. 관리자의 승인을 기다려주세요.",
            "user_id": user.id,
            "email": user.email
        })

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="회원가입 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.post("/login")
async def login(credentials: UserLogin):
    """로그인 API.

    이메일과 비밀번호로 로그인하여 JWT 토큰 반환.

    Args:
        credentials: 로그인 정보 (이메일, 비밀번호)

    Returns:
        표준 API 응답 (JWT 토큰 및 사용자 정보)
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # 디버깅: 입력된 이메일 로깅
        logger.info(f"[LOGIN] 로그인 시도 - email: {credentials.email}")
        
        # 사용자 인증
        user = authenticate_user(credentials.email, credentials.password)
        if not user:
            logger.warning(f"[LOGIN] 인증 실패 - email: {credentials.email}")
            return error_response(
                code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                http_status=401,
                message="이메일 또는 비밀번호가 올바르지 않습니다.",
                hint="입력 정보를 다시 확인해주세요."
            )

        # 계정 활성화 확인
        if not user.is_active:
            logger.warning(f"[LOGIN] 계정 비활성화 - email: {credentials.email}, is_active: {user.is_active}")
            return error_response(
                code=ErrorCode.AUTH_ACCOUNT_INACTIVE,
                http_status=403,
                message="계정이 활성화되지 않았습니다.",
                hint="관리자의 승인을 기다려주세요."
            )

        # JWT 토큰 생성
        access_token = create_access_token(
            data={"user_id": user.id, "email": user.email}
        )
        
        logger.info(f"[LOGIN] 로그인 성공 - user_id: {user.id}, email: {user.email}")

        user_response = UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            is_admin=user.is_admin,
            password_reset_required=user.password_reset_required,
            created_at=user.created_at
        )

        return success_response({
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_response.dict()
        })

    except Exception as e:
        logger.error(f"[LOGIN] 예외 발생: {str(e)}", exc_info=True)
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="로그인 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.get("/me")
async def get_me(current_user = Depends(get_current_active_user)):
    """현재 로그인한 사용자 정보 조회.

    Args:
        current_user: JWT 토큰에서 추출한 현재 사용자

    Returns:
        표준 API 응답 (사용자 정보)
    """
    try:
        user_response = UserResponse(
            id=current_user.id,
            email=current_user.email,
            username=current_user.username,
            is_active=current_user.is_active,
            is_admin=current_user.is_admin,
            password_reset_required=current_user.password_reset_required,
            created_at=current_user.created_at
        )

        return success_response(user_response.dict())

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="사용자 정보 조회 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )


@router.post("/logout")
async def logout(current_user = Depends(get_current_user)):
    """로그아웃 API.

    JWT는 stateless이므로 클라이언트에서 토큰 삭제 처리.

    Args:
        current_user: JWT 토큰에서 추출한 현재 사용자

    Returns:
        표준 API 응답 (로그아웃 성공 메시지)
    """
    return success_response({
        "message": "로그아웃되었습니다."
    })


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user = Depends(get_current_user)
):
    """비밀번호 변경 API.

    현재 비밀번호 확인 후 새 비밀번호로 변경.
    변경 후 password_reset_required 플래그 해제.

    Args:
        password_data: 현재 비밀번호 및 새 비밀번호
        current_user: JWT 토큰에서 추출한 현재 사용자

    Returns:
        표준 API 응답 (변경 성공 또는 에러)
    """
    try:
        # 현재 비밀번호 확인
        if not verify_password(password_data.current_password, current_user.hashed_password):
            return error_response(
                code=ErrorCode.AUTH_INVALID_PASSWORD,
                http_status=400,
                message="현재 비밀번호가 올바르지 않습니다.",
                hint="현재 사용 중인 비밀번호를 확인해주세요."
            )

        # 새 비밀번호 해싱
        new_hashed_password = hash_password(password_data.new_password)

        # 비밀번호 업데이트
        success = UserDB.update_password(current_user.id, new_hashed_password)
        if not success:
            return error_response(
                code=ErrorCode.SERVER_DATABASE_ERROR,
                http_status=500,
                message="비밀번호 업데이트에 실패했습니다."
            )

        # password_reset_required 플래그 해제
        update = UserUpdate(password_reset_required=False)
        UserDB.update_user(current_user.id, update)

        return success_response({
            "message": "비밀번호가 성공적으로 변경되었습니다."
        })

    except Exception as e:
        return error_response(
            code=ErrorCode.SERVER_INTERNAL_ERROR,
            http_status=500,
            message="비밀번호 변경 중 오류가 발생했습니다.",
            details={"error": str(e)}
        )
