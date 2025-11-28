"""Report section metadata models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SectionType(str, Enum):
    """섹션 타입 정의."""

    TITLE = "TITLE"
    DATE = "DATE"
    BACKGROUND = "BACKGROUND"
    MAIN_CONTENT = "MAIN_CONTENT"
    SUMMARY = "SUMMARY"
    CONCLUSION = "CONCLUSION"
    SECTION = "SECTION"  # 템플릿 기반 커스텀 섹션


class SourceType(str, Enum):
    """섹션 출처 타입."""

    BASIC = "basic"  # 기본 고정 섹션
    TEMPLATE = "template"  # 템플릿 기반 섹션
    SYSTEM = "system"  # 시스템이 생성한 섹션 (DATE)


class SectionMetadata(BaseModel):
    """개별 섹션 메타정보."""

    id: str = Field(..., description="섹션 ID (예: TITLE, {{MARKET_ANALYSIS}})")
    type: str = Field(..., description="섹션 타입 (BASIC: 고정값, TEMPLATE: 동적값)")
    content: str = Field(..., min_length=1, description="섹션 내용")
    order: int = Field(..., ge=1, description="섹션 순서 (1-based)")
    placeholder_key: Optional[str] = Field(
        None, description="템플릿 placeholder_key ({{KEY}} 형식)"
    )
    source_type: SourceType = Field(..., description="섹션 출처 (basic, template, system)")
    max_length: Optional[int] = Field(
        None, description="최대 문자 길이 (PlaceholderMetadata에서)"
    )
    min_length: Optional[int] = Field(
        None, description="최소 문자 길이 (PlaceholderMetadata에서)"
    )
    description: Optional[str] = Field(None, description="섹션 설명")
    example: Optional[str] = Field(None, description="예시 값")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "TITLE",
                "type": "TITLE",
                "content": "2025년 디지털뱅킹 트렌드",
                "order": 1,
                "source_type": "basic",
            }
        }


class StructuredReportResponse(BaseModel):
    """구조화된 보고서 응답 (JSON)."""

    sections: List[SectionMetadata] = Field(..., description="섹션 배열")
    metadata: Optional[dict] = Field(None, description="메타데이터 (생성일, 모델 등)")

    class Config:
        json_schema_extra = {
            "example": {
                "sections": [
                    {
                        "id": "TITLE",
                        "type": "TITLE",
                        "content": "2025년 디지털뱅킹 트렌드 분석",
                        "order": 1,
                        "source_type": "basic",
                    },
                    {
                        "id": "DATE",
                        "type": "DATE",
                        "content": "2025.11.28",
                        "order": 2,
                        "source_type": "system",
                    },
                ],
                "metadata": {
                    "generated_at": "2025-11-28T14:30:00",
                    "model": "claude-sonnet-4-5-20250929",
                    "total_sections": 2,
                },
            }
        }

