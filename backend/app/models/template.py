"""Template 모델 정의.

사용자 커스텀 HWPX 템플릿과 플레이스홀더 관리를 위한 Pydantic 모델들입니다.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PlaceholderBase(BaseModel):
    """플레이스홀더 기본 모델."""

    placeholder_key: str = Field(..., description="플레이스홀더 키 (예: {{TITLE}})")


class PlaceholderCreate(PlaceholderBase):
    """플레이스홀더 생성 모델."""

    template_id: int = Field(..., description="템플릿 ID")
    sort: Optional[int] = Field(None, description="정렬 순서 (0-based index)")


class Placeholder(PlaceholderCreate):
    """플레이스홀더 응답 모델."""

    id: int
    sort: int = Field(0, description="정렬 순서 (0-based index)")
    created_at: datetime

    class Config:
        from_attributes = True


class PlaceholderResponse(BaseModel):
    """API 응답용 플레이스홀더 모델."""

    key: str = Field(..., description="플레이스홀더 키 (예: {{TITLE}})")


class TemplateBase(BaseModel):
    """템플릿 기본 모델."""

    title: str = Field(..., description="템플릿 제목")
    description: Optional[str] = Field(None, description="템플릿 설명")


class TemplateCreate(TemplateBase):
    """템플릿 생성 모델 (내부용)."""

    filename: str = Field(..., description="원본 파일명")
    file_path: str = Field(..., description="저장 경로")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    sha256: str = Field(..., description="파일 무결성 체크용 해시")
    prompt_user: Optional[str] = Field(None, description="사용자가 정의한 커스텀 System Prompt (선택)")
    prompt_system: Optional[str] = Field(None, description="동적 생성된 System Prompt")


class Template(TemplateCreate):
    """템플릿 응답 모델."""

    id: int
    user_id: int
    is_active: bool = Field(True, description="활성화 상태")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadTemplateRequest(BaseModel):
    """템플릿 업로드 요청 모델."""

    title: str = Field(..., description="템플릿 제목")


class UploadTemplateResponse(BaseModel):
    """템플릿 업로드 응답 모델."""

    id: int = Field(..., description="템플릿 ID")
    title: str = Field(..., description="템플릿 제목")
    filename: str = Field(..., description="파일명")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    placeholders: List[PlaceholderResponse] = Field(..., description="플레이스홀더 목록")
    prompt_user: Optional[str] = Field(None, description="사용자가 정의한 커스텀 System Prompt (선택)")
    prompt_system: Optional[str] = Field(None, description="동적 생성된 System Prompt")
    created_at: datetime = Field(..., description="생성 일시")


class TemplateListResponse(BaseModel):
    """템플릿 목록 응답 모델."""

    id: int = Field(..., description="템플릿 ID")
    title: str = Field(..., description="템플릿 제목")
    filename: str = Field(..., description="파일명")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    created_at: datetime = Field(..., description="생성 일시")


class TemplateDetailResponse(BaseModel):
    """템플릿 상세 응답 모델."""

    id: int = Field(..., description="템플릿 ID")
    title: str = Field(..., description="템플릿 제목")
    filename: str = Field(..., description="파일명")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    placeholders: List[PlaceholderResponse] = Field(..., description="플레이스홀더 목록")
    prompt_system: Optional[str] = Field(None, description="동적 생성된 System Prompt")
    prompt_user: Optional[str] = Field(None, description="사용자 정의 System Prompt")
    created_at: datetime = Field(..., description="생성 일시")


class AdminTemplateResponse(BaseModel):
    """관리자용 템플릿 응답 모델."""

    id: int = Field(..., description="템플릿 ID")
    title: str = Field(..., description="템플릿 제목")
    username: str = Field(..., description="사용자명")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    placeholder_count: int = Field(..., description="플레이스홀더 개수")
    prompt_system: Optional[str] = Field(None, description="동적 생성된 System Prompt")
    created_at: datetime = Field(..., description="생성 일시")


class UpdatePromptSystemRequest(BaseModel):
    """시스템 프롬프트 수정 요청 모델."""

    prompt_system: str = Field(..., description="새로운 시스템 프롬프트")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt_system": "새로운 시스템 프롬프트 텍스트"
            }
        }


class UpdatePromptUserRequest(BaseModel):
    """사용자 프롬프트 수정 요청 모델."""

    prompt_user: str = Field(..., description="새로운 사용자 프롬프트")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt_user": "새로운 사용자 프롬프트 텍스트"
            }
        }


class UpdatePromptResponse(BaseModel):
    """프롬프트 수정 응답 모델."""

    id: int = Field(..., description="템플릿 ID")
    title: str = Field(..., description="템플릿 제목")
    prompt_system: Optional[str] = Field(None, description="시스템 프롬프트")
    prompt_user: Optional[str] = Field(None, description="사용자 프롬프트")
    updated_at: datetime = Field(..., description="수정 일시")


class RegeneratePromptResponse(BaseModel):
    """프롬프트 재생성 응답 모델."""

    id: int = Field(..., description="템플릿 ID")
    prompt_system: Optional[str] = Field(None, description="재생성된 시스템 프롬프트")
    regenerated_at: datetime = Field(..., description="재생성 일시")
