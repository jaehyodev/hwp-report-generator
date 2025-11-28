"""
테스트: Claude API Structured Outputs 통합

Unit Spec: backend/doc/specs/20251128_structured_outputs_integration.md
테스트 계획: 8개 TC (Schema 2개 + Processing 2개 + Conversion 1개 + Error 1개 + API 2개)
"""

import pytest
import json
import logging
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from app.models.report_section import (
    SectionMetadata,
    SectionType,
    SourceType,
    StructuredReportResponse,
)
from app.utils.structured_client import StructuredClaudeClient
from app.utils.prompts import create_section_schema
from app.utils.markdown_builder import build_report_md_from_json

logger = logging.getLogger(__name__)


# =====================================================================
# TC-001: Structured Output JSON Schema 빌드 (BASIC)
# =====================================================================

class TestJSONSchemaGeneration:
    """JSON Schema 빌드 테스트"""

    def test_tc_001_basic_schema_generation(self):
        """TC-001: BASIC 모드 JSON Schema 생성 및 검증

        목표: BASIC 모드 JSON Schema 생성 및 검증
        - type enum = 고정 6개
        - source_type enum = ["basic", "system"]
        """
        # Arrange
        client = StructuredClaudeClient()
        section_schema = {"sections": [
            {"id": "TITLE", "type": "TITLE", "order": 1},
            {"id": "DATE", "type": "DATE", "order": 2},
            {"id": "BACKGROUND", "type": "BACKGROUND", "order": 3},
            {"id": "MAIN_CONTENT", "type": "MAIN_CONTENT", "order": 4},
            {"id": "SUMMARY", "type": "SUMMARY", "order": 5},
            {"id": "CONCLUSION", "type": "CONCLUSION", "order": 6},
        ]}
        source_type = "basic"

        # Act
        json_schema = client._build_json_schema(section_schema, source_type)

        # Assert
        assert json_schema is not None
        assert json_schema["type"] == "object"
        assert "sections" in json_schema["properties"]

        # type enum 검증
        type_enum = json_schema["properties"]["sections"]["items"]["properties"]["type"]["enum"]
        assert "TITLE" in type_enum
        assert "DATE" in type_enum
        assert "BACKGROUND" in type_enum
        assert "MAIN_CONTENT" in type_enum
        assert "SUMMARY" in type_enum
        assert "CONCLUSION" in type_enum
        assert len(type_enum) == 6  # ✅ 고정값

        # source_type enum 검증
        source_type_enum = json_schema["properties"]["sections"]["items"]["properties"]["source_type"]["enum"]
        assert "basic" in source_type_enum
        assert "system" in source_type_enum

        logger.info("✅ TC-001 PASSED: BASIC schema generation")

    def test_tc_001b_template_schema_generation(self):
        """TC-001B: TEMPLATE 모드 JSON Schema 생성 및 검증 (type = 자유형)

        목표: TEMPLATE 모드에서 type enum 제약이 없어야 함
        - type = 문자열 자유형 (enum 없음)
        - source_type enum = ["template", "system"]
        """
        # Arrange
        client = StructuredClaudeClient()
        section_schema = {
            "sections": [
                {"id": "TITLE", "type": "TITLE", "order": 1},
                {"id": "MARKET_ANALYSIS", "type": "MARKET_ANALYSIS", "order": 2},
                {"id": "CUSTOM_SECTION", "type": "CUSTOM_SECTION", "order": 3},
            ]
        }
        source_type = "template"

        # Act
        json_schema = client._build_json_schema(section_schema, source_type)

        # Assert
        assert json_schema is not None

        # type 필드 검증 (enum이 없어야 함 - 자유형)
        type_field = json_schema["properties"]["sections"]["items"]["properties"]["type"]
        assert type_field["type"] == "string"
        assert "enum" not in type_field  # ✅ enum 제약 없음

        # source_type enum 검증
        source_type_enum = json_schema["properties"]["sections"]["items"]["properties"]["source_type"]["enum"]
        assert "template" in source_type_enum
        assert "system" in source_type_enum

        logger.info("✅ TC-001B PASSED: TEMPLATE schema generation")


# =====================================================================
# TC-002: 유효한 Structured Output 응답 처리
# =====================================================================

class TestResponseProcessing:
    """Structured Output 응답 처리 테스트"""

    def test_tc_002_valid_structured_response(self):
        """TC-002: 유효한 Structured Output 응답 파싱

        목표: Claude API의 Structured Output 응답을 StructuredReportResponse로 변환
        """
        # Arrange
        client = StructuredClaudeClient()
        response_json = {
            "sections": [
                {
                    "id": "TITLE",
                    "type": "TITLE",
                    "content": "2025년 AI 시장 분석 보고서",
                    "order": 1,
                    "source_type": "basic"
                },
                {
                    "id": "BACKGROUND",
                    "type": "BACKGROUND",
                    "content": "AI 시장이 급속도로 성장하고 있습니다...",
                    "order": 3,
                    "source_type": "basic"
                },
                {
                    "id": "MAIN_CONTENT",
                    "type": "MAIN_CONTENT",
                    "content": "주요 세그먼트별 분석: 1) 제너러티브 AI...",
                    "order": 4,
                    "source_type": "basic"
                },
                {
                    "id": "SUMMARY",
                    "type": "SUMMARY",
                    "content": "핵심 내용 요약입니다.",
                    "order": 5,
                    "source_type": "basic"
                },
                {
                    "id": "CONCLUSION",
                    "type": "CONCLUSION",
                    "content": "결론 및 제언입니다.",
                    "order": 6,
                    "source_type": "basic"
                }
            ]
        }

        # Act
        result = client._process_response(response_json, "AI 시장 분석", "basic")

        # Assert
        assert isinstance(result, StructuredReportResponse)
        assert len(result.sections) >= 5  # DATE 섹션 추가되므로 >= 5
        assert result.sections[0].id == "TITLE"
        assert result.sections[0].type == "TITLE"
        assert "DATE" in [s.id for s in result.sections]  # 시스템 DATE 확인
        assert result.metadata is not None
        assert result.metadata["source_type"] == "basic"

        logger.info(f"✅ TC-002 PASSED: Valid structured response - {len(result.sections)} sections")

    def test_tc_003_structured_response_with_template_types(self):
        """TC-003: TEMPLATE 모드 동적 타입 처리

        목표: TEMPLATE 모드에서 동적 type 값 처리
        """
        # Arrange
        client = StructuredClaudeClient()
        response_json = {
            "sections": [
                {
                    "id": "TITLE",
                    "type": "TITLE",
                    "content": "시장 분석 보고서",
                    "order": 1,
                    "source_type": "template"
                },
                {
                    "id": "MARKET_ANALYSIS",
                    "type": "MARKET_ANALYSIS",  # ⭐ 동적 type (enum이 아님)
                    "content": "시장 분석 내용...",
                    "order": 3,
                    "source_type": "template"
                },
                {
                    "id": "FINANCIAL_ANALYSIS",
                    "type": "FINANCIAL_ANALYSIS",  # ⭐ 동적 type
                    "content": "재무 분석 내용...",
                    "order": 4,
                    "source_type": "template"
                }
            ]
        }

        # Act
        result = client._process_response(response_json, "시장 분석", "template")

        # Assert
        assert isinstance(result, StructuredReportResponse)
        assert len(result.sections) >= 3

        # 동적 type 값이 문자열로 유지되어야 함
        market_section = next((s for s in result.sections if s.id == "MARKET_ANALYSIS"), None)
        assert market_section is not None
        assert market_section.type == "MARKET_ANALYSIS"
        assert isinstance(market_section.type, str)

        logger.info("✅ TC-003 PASSED: Template dynamic types")


# =====================================================================
# TC-004: 마크다운 변환 (JSON → Markdown)
# =====================================================================

class TestMarkdownConversion:
    """JSON → Markdown 변환 테스트"""

    def test_tc_004_json_to_markdown_conversion(self):
        """TC-004: StructuredReportResponse → Markdown 변환

        목표: JSON 구조를 마크다운으로 정확히 변환
        """
        # Arrange
        response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="TITLE",
                    type="TITLE",
                    content="2025년 AI 시장 분석",
                    order=1,
                    source_type=SourceType.BASIC
                ),
                SectionMetadata(
                    id="DATE",
                    type="DATE",
                    content="2025.11.28",
                    order=2,
                    source_type=SourceType.SYSTEM
                ),
                SectionMetadata(
                    id="BACKGROUND",
                    type="BACKGROUND",
                    content="AI 시장 배경...",
                    order=3,
                    source_type=SourceType.BASIC
                ),
                SectionMetadata(
                    id="MAIN_CONTENT",
                    type="MAIN_CONTENT",
                    content="주요 내용...",
                    order=4,
                    source_type=SourceType.BASIC
                ),
                SectionMetadata(
                    id="SUMMARY",
                    type="SUMMARY",
                    content="요약...",
                    order=5,
                    source_type=SourceType.BASIC
                ),
                SectionMetadata(
                    id="CONCLUSION",
                    type="CONCLUSION",
                    content="결론...",
                    order=6,
                    source_type=SourceType.BASIC
                ),
            ]
        )

        # Act
        markdown = build_report_md_from_json(response)

        # Assert
        assert markdown is not None
        assert len(markdown) > 0
        assert "# 2025년 AI 시장 분석" in markdown  # TITLE
        assert "생성일: 2025.11.28" in markdown  # DATE
        assert "배경 및 목적" in markdown or "BACKGROUND" in markdown  # BACKGROUND
        assert "주요 내용" in markdown or "MAIN_CONTENT" in markdown  # MAIN_CONTENT

        logger.info(f"✅ TC-004 PASSED: JSON to markdown - {len(markdown)} chars")


# =====================================================================
# TC-005: 에러 처리 (유효하지 않은 입력)
# =====================================================================

class TestErrorHandling:
    """에러 처리 테스트"""

    def test_tc_005_invalid_source_type(self):
        """TC-005: 유효하지 않은 source_type 처리

        목표: 유효하지 않은 source_type에 대해 ValueError 발생
        """
        # Arrange
        client = StructuredClaudeClient()
        section_schema = {"sections": []}
        invalid_source_type = "invalid_type"

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown source_type"):
            client._build_json_schema(section_schema, invalid_source_type)

        logger.info("✅ TC-005 PASSED: Invalid source_type error handling")

    def test_tc_006_empty_sections(self):
        """TC-006: 빈 sections 처리

        목표: 빈 sections 배열에 대한 처리
        """
        # Arrange
        client = StructuredClaudeClient()
        response_json = {"sections": []}

        # Act
        result = client._process_response(response_json, "Test", "basic")

        # Assert
        assert isinstance(result, StructuredReportResponse)
        # DATE 섹션만 추가되어야 함
        assert len(result.sections) >= 1
        assert result.sections[0].id == "DATE"

        logger.info("✅ TC-006 PASSED: Empty sections handling")


# =====================================================================
# TC-007: 성능 검증
# =====================================================================

class TestPerformance:
    """성능 검증 테스트"""

    def test_tc_007_schema_generation_performance(self):
        """TC-007: JSON Schema 생성 성능 (< 100ms)

        목표: Schema 생성이 충분히 빨라야 함
        """
        # Arrange
        client = StructuredClaudeClient()
        section_schema = {"sections": [{"id": f"SEC_{i}", "type": "SECTION", "order": i} for i in range(20)]}

        # Act
        start = time.time()
        json_schema = client._build_json_schema(section_schema, "basic")
        elapsed_ms = (time.time() - start) * 1000

        # Assert
        assert json_schema is not None
        assert elapsed_ms < 100, f"Schema generation took {elapsed_ms}ms (should be < 100ms)"

        logger.info(f"✅ TC-007 PASSED: Schema generation - {elapsed_ms:.2f}ms")

    def test_tc_008_response_processing_performance(self):
        """TC-008: Response 처리 성능 (< 100ms)

        목표: Response 처리가 충분히 빨라야 함
        """
        # Arrange
        client = StructuredClaudeClient()
        response_json = {
            "sections": [
                {
                    "id": f"SEC_{i}",
                    "type": "SECTION",
                    "content": f"Content for section {i}",
                    "order": i + 1,
                    "source_type": "basic"
                }
                for i in range(10)
            ]
        }

        # Act
        start = time.time()
        result = client._process_response(response_json, "Test", "basic")
        elapsed_ms = (time.time() - start) * 1000

        # Assert
        assert isinstance(result, StructuredReportResponse)
        assert elapsed_ms < 100, f"Response processing took {elapsed_ms}ms (should be < 100ms)"

        logger.info(f"✅ TC-008 PASSED: Response processing - {elapsed_ms:.2f}ms")


# =====================================================================
# Integration Tests - Compatibility
# =====================================================================

class TestCompatibility:
    """호환성 테스트"""

    def test_backward_compatibility_with_existing_tests(self):
        """기존 테스트와의 호환성 확인

        목표: 기존 build_report_md_from_json() 함수와 호환성 유지
        """
        # Arrange
        sections = [
            SectionMetadata(
                id="TITLE",
                type="TITLE",
                content="테스트 보고서",
                order=1,
                source_type=SourceType.BASIC
            ),
        ]
        response = StructuredReportResponse(sections=sections)

        # Act
        markdown = build_report_md_from_json(response)

        # Assert
        assert markdown is not None
        assert "# 테스트 보고서" in markdown

        logger.info("✅ COMPATIBILITY PASSED: Backward compatibility confirmed")

    def test_string_type_field_compatibility(self):
        """SectionMetadata type 필드가 str이어야 함

        목표: type 필드가 문자열이어야 동적 값 지원 가능
        """
        # Arrange & Act
        section = SectionMetadata(
            id="CUSTOM",
            type="CUSTOM_TYPE",  # ⭐ 문자열 가능
            content="Content",
            order=1,
            source_type=SourceType.BASIC
        )

        # Assert
        assert isinstance(section.type, str)
        assert section.type == "CUSTOM_TYPE"

        logger.info("✅ STRING_TYPE PASSED: type field is string")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
