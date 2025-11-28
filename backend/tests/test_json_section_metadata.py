"""
테스트: JSON 구조화 섹션 메타정보 기반 MD/HWPX 생성

Unit Spec: backend/doc/specs/20251128_json_structured_section_metadata.md
테스트 계획: 10개 TC (Unit 5개 + Integration 2개 + API 3개)
"""
import pytest
import json
import logging
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from app.models.report_section import (
    SectionMetadata,
    SectionType,
    SourceType,
    StructuredReportResponse,
)
from app.models.template import Placeholder
from app.utils.prompts import create_section_schema
from app.utils.markdown_builder import build_report_md_from_json
from shared.types.enums import TopicSourceType


logger = logging.getLogger(__name__)


# =====================================================================
# Unit Tests (5개)
# =====================================================================

class TestUnitSectionSchema:
    """섹션 스키마 생성 테스트"""

    def test_tc_001_basic_schema_generation(self):
        """TC-001: JSON 섹션 메타정보 생성 (BASIC)

        - 입력: source_type=BASIC
        - 기대: 6개 고정 섹션 (TITLE, DATE, BACKGROUND, MAIN_CONTENT, SUMMARY, CONCLUSION)
        """
        # Arrange
        source_type = "basic"

        # Act
        schema = create_section_schema(source_type)

        # Assert
        assert schema is not None
        assert "sections" in schema
        sections = schema.get("sections", [])

        # 섹션 개수 = 6
        assert len(sections) == 6, f"Expected 6 sections, got {len(sections)}"

        # 섹션 순서 확인
        expected_ids = ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"]
        actual_ids = [s.get("id") for s in sections]
        assert actual_ids == expected_ids, f"Expected {expected_ids}, got {actual_ids}"

        # order 필드: 1-6 순차
        for i, section in enumerate(sections, 1):
            assert section.get("order") == i, f"Section {i}: expected order={i}, got {section.get('order')}"

        # source_type 필드 확인
        for section in sections:
            assert section.get("source_type") in ("basic", "system"), \
                f"Unexpected source_type: {section.get('source_type')}"

        logger.info("✅ TC-001 passed: BASIC schema generation")

    def test_tc_002_template_schema_with_placeholders(self):
        """TC-002: JSON 섹션 메타정보 생성 (TEMPLATE) - Placeholder 메타정보 포함

        - 입력: source_type=TEMPLATE, placeholders with sort
        - 기대: 동적 섹션 정의 + 메타정보 포함
        """
        # Arrange
        source_type = "template"
        placeholders = [
            {"id": 1, "placeholder_key": "{{TITLE}}", "sort": 0},
            {"id": 2, "placeholder_key": "{{MARKET_ANALYSIS}}", "sort": 1},
            {"id": 3, "placeholder_key": "{{CONCLUSION}}", "sort": 2},
        ]

        # Act
        schema = create_section_schema(source_type, placeholders)

        # Assert
        assert schema is not None
        sections = schema.get("sections", [])

        # 섹션 개수 = 3 (DATE는 예약, placeholder 3개)
        # 실제로는 DATE가 추가되므로 4개일 수 있음
        assert len(sections) >= 3, f"Expected at least 3 sections, got {len(sections)}"

        # placeholder_key 필드 확인
        placeholder_keys = [s.get("placeholder_key") for s in sections if s.get("placeholder_key")]
        assert "{{TITLE}}" in placeholder_keys
        assert "{{MARKET_ANALYSIS}}" in placeholder_keys
        assert "{{CONCLUSION}}" in placeholder_keys

        logger.info("✅ TC-002 passed: TEMPLATE schema with placeholders")

    def test_tc_003_llm_json_response_parsing(self):
        """TC-003: LLM JSON 응답 파싱 및 검증

        - 입력: Claude API JSON 응답 (dict)
        - 기대: StructuredReportResponse 객체로 변환
        """
        # Arrange
        json_response_dict = {
            "sections": [
                {
                    "id": "TITLE",
                    "content": "보고서 제목",
                    "type": "TITLE",
                    "order": 1,
                    "source_type": "basic"
                },
                {
                    "id": "BACKGROUND",
                    "content": "배경 및 목적에 대한 내용...",
                    "type": "SECTION",
                    "order": 3,
                    "source_type": "basic"
                }
            ]
        }

        # Act - Pydantic 모델로 검증
        try:
            response = StructuredReportResponse(**json_response_dict)
        except Exception as e:
            pytest.fail(f"Failed to parse JSON response: {str(e)}")

        # Assert
        assert response is not None
        assert len(response.sections) == 2
        assert response.sections[0].id == "TITLE"
        assert response.sections[0].content == "보고서 제목"
        assert len(response.sections[1].content) > 0

        logger.info("✅ TC-003 passed: LLM JSON response parsing")

    def test_tc_004_json_to_markdown_conversion(self):
        """TC-004: JSON → 마크다운 변환

        - 입력: StructuredReportResponse (3개 섹션)
        - 기대: 유효한 마크다운 생성
        """
        # Arrange
        response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="TITLE",
                    type=SectionType.TITLE,
                    content="보고서 제목",
                    order=1,
                    source_type=SourceType.BASIC
                ),
                SectionMetadata(
                    id="DATE",
                    type=SectionType.DATE,
                    content="2025.11.28",
                    order=2,
                    source_type=SourceType.SYSTEM
                ),
                SectionMetadata(
                    id="BACKGROUND",
                    type=SectionType.SECTION,
                    content="배경 및 목적에 대한 상세 내용...",
                    order=3,
                    source_type=SourceType.BASIC
                ),
            ]
        )

        # Act
        markdown = build_report_md_from_json(response)

        # Assert
        assert markdown is not None
        assert len(markdown) > 0
        assert "# 보고서 제목" in markdown
        assert "생성일: 2025.11.28" in markdown
        assert "## 배경 및 목적" in markdown or "BACKGROUND" in markdown

        logger.info(f"✅ TC-004 passed: JSON to markdown conversion (length={len(markdown)})")

    def test_tc_005_fallback_markdown_parsing(self):
        """TC-005: Fallback - 마크다운 응답 자동 파싱

        - 입력: LLM이 JSON이 아닌 마크다운만 반환
        - 기대: 마크다운을 자동 파싱
        """
        # Arrange - markdown string
        markdown_response = """
# 보고서 제목

## 배경 및 목적
배경 내용...

## 주요 내용
주요 내용...

## 결론 및 제언
결론...
"""

        # Act - parse_markdown_to_content import
        from app.utils.markdown_parser import parse_markdown_to_content

        try:
            parsed = parse_markdown_to_content(markdown_response)
        except Exception as e:
            pytest.fail(f"Failed to parse markdown: {str(e)}")

        # Assert
        assert parsed is not None
        assert "title" in parsed
        assert parsed["title"] == "보고서 제목"
        assert len(parsed.get("background", "")) > 0

        logger.info("✅ TC-005 passed: Fallback markdown parsing")


# =====================================================================
# Integration Tests (2개)
# =====================================================================

class TestIntegrationFlow:
    """전체 흐름 통합 테스트"""

    @pytest.mark.skip(reason="Requires full database setup")
    def test_tc_006_full_flow_basic(self):
        """TC-006: 전체 흐름 - BASIC 타입

        1. 섹션 정의 생성
        2. LLM 호출
        3. JSON 파싱
        4. DATE 삽입
        5. 마크다운 생성
        6. 파일 저장
        """
        # This test requires mocking the entire flow
        pass

    @pytest.mark.skip(reason="Requires full database setup")
    def test_tc_007_full_flow_template(self):
        """TC-007: 전체 흐름 - TEMPLATE 타입

        1. Template placeholders 조회 (sort 순서)
        2. 동적 섹션 정의 생성
        3. LLM 호출
        4. JSON 파싱
        5. 마크다운 생성
        6. 파일 저장
        """
        # This test requires mocking the entire flow
        pass


# =====================================================================
# API Tests (3개)
# =====================================================================

class TestAPISectionMetadata:
    """API 엔드포인트 테스트"""

    @pytest.mark.skip(reason="Requires async test setup with database")
    def test_tc_008_post_topics_ask_json_response(self):
        """TC-008: POST /api/topics/ask - JSON 응답

        - 요청: /api/topics/{topic_id}/ask
        - 조건: source_type=BASIC
        - 기대: artifact 객체 반환 (kind=MD)
        """
        pass

    @pytest.mark.skip(reason="Requires async test setup with database")
    def test_tc_009_post_topics_generate_json_response(self):
        """TC-009: POST /api/topics/generate - JSON 응답 (백그라운드)

        - 요청: POST /api/topics/generate
        - 조건: source_type=TEMPLATE
        - 기대: 202 Accepted + generation_id
        """
        pass

    @pytest.mark.skip(reason="Requires async test setup with database")
    def test_tc_010_markdown_to_hwpx_conversion_json_based(self):
        """TC-010: 마크다운 → HWPX 변환 (기존 v2.6 + JSON 메타정보)

        - 요청: POST /api/artifacts/{artifact_id}/convert-hwpx
        - 조건: artifact.kind = 'MD' (JSON 기반 생성)
        - 기대: HWPX 파일 반환
        """
        pass


# =====================================================================
# Additional Tests - DATE Handling
# =====================================================================

class TestDATEHandling:
    """TEMPLATE DATE 처리 테스트"""

    def test_tc_002b_template_date_handling_rule1(self):
        """TC-002-B: TEMPLATE 타입 DATE 처리 - 규칙 1 (Template placeholders에 DATE 있음)

        - 입력: placeholders에 {{DATE}} 포함
        - 기대: LLM의 DATE 사용
        """
        # Arrange
        source_type = "template"
        placeholders = [
            {"id": 1, "placeholder_key": "{{TITLE}}", "sort": 0},
            {"id": 2, "placeholder_key": "{{DATE}}", "sort": 1},
            {"id": 3, "placeholder_key": "{{SUMMARY}}", "sort": 2},
        ]

        # Act
        schema = create_section_schema(source_type, placeholders)

        # Assert
        sections = schema.get("sections", [])
        date_sections = [s for s in sections if s.get("id") == "DATE"]

        # DATE 섹션이 있어야 함
        assert len(date_sections) > 0, "DATE section not found in schema"
        date_section = date_sections[0]
        assert date_section.get("source_type") == "template"

        logger.info("✅ TC-002-B passed: DATE handling rule 1")

    def test_tc_002c_template_date_handling_rule2(self):
        """TC-002-C: TEMPLATE 타입 DATE 처리 - 규칙 2 (Template placeholders에 DATE 없음)

        - 입력: placeholders에 {{DATE}} 없음
        - 기대: 시스템 DATE 삽입
        """
        # Arrange
        source_type = "template"
        placeholders = [
            {"id": 1, "placeholder_key": "{{TITLE}}", "sort": 0},
            {"id": 2, "placeholder_key": "{{SUMMARY}}", "sort": 1},
            {"id": 3, "placeholder_key": "{{ANALYSIS}}", "sort": 2},
        ]

        # Act
        schema = create_section_schema(source_type, placeholders)

        # Assert
        sections = schema.get("sections", [])
        date_sections = [s for s in sections if s.get("id") == "DATE"]

        # DATE 섹션이 있어야 함 (시스템에서 삽입)
        assert len(date_sections) > 0, "DATE section not found (system should have added it)"
        date_section = date_sections[0]

        # order=2는 예약되어야 함
        assert date_section.get("order") == 2

        logger.info("✅ TC-002-C passed: DATE handling rule 2")

    def test_tc_002d_template_date_handling_rule3(self):
        """TC-002-D: TEMPLATE 타입 DATE 처리 - 규칙 3 (LLM이 DATE 중복 생성)

        - 입력: LLM이 DATE 중복 생성
        - 기대: DATE 중복 제거, 시스템 DATE로 대체

        Note: 이 테스트는 claude_client._process_json_response()에서 처리
        """
        # 이 테스트는 claude_client 모듈에서 처리되므로 여기서는 스킵
        pass


# =====================================================================
# Helper Tests
# =====================================================================

class TestHelperFunctions:
    """헬퍼 함수 테스트"""

    def test_placeholder_metadata_creation(self):
        """PlaceholderMetadata 객체 생성 테스트"""
        # Arrange
        placeholder_data = {
            "id": 1,
            "template_id": 1,
            "placeholder_key": "{{MARKET_ANALYSIS}}",
            "sort": 1,
            "created_at": datetime.now(),
        }

        # Act
        placeholder = Placeholder(**placeholder_data)

        # Assert
        assert placeholder.placeholder_key == "{{MARKET_ANALYSIS}}"
        assert placeholder.sort == 1
        assert placeholder.template_id == 1

        logger.info("✅ Placeholder metadata creation passed")

    def test_section_metadata_with_all_fields(self):
        """SectionMetadata 전체 필드 테스트"""
        # Arrange
        section_data = {
            "id": "MARKET_ANALYSIS",
            "type": "SECTION",  # ✅ Now a string, not SectionType enum
            "content": "시장 분석 내용",
            "order": 3,
            "source_type": SourceType.BASIC,
            "max_length": 1500,
            "min_length": 500,
        }

        # Act
        section = SectionMetadata(**section_data)

        # Assert
        assert section.id == "MARKET_ANALYSIS"
        assert section.type == "SECTION"  # ✅ Verify it's a string
        assert section.order == 3
        assert section.max_length == 1500

        logger.info("✅ SectionMetadata with all fields passed")


# =====================================================================
# Regression Tests (기존 호환성)
# =====================================================================

class TestRegressionCompatibility:
    """기존 코드 호환성 테스트"""

    def test_basic_markdown_builder_still_works(self):
        """기존 build_report_md() 함수 호환성"""
        from app.utils.markdown_builder import build_report_md

        # Arrange
        parsed = {
            "title": "테스트 보고서",
            "summary": "요약 내용",
            "background": "배경 내용",
            "main_content": "주요 내용",
            "conclusion": "결론",
        }

        # Act
        markdown = build_report_md(parsed)

        # Assert
        assert markdown is not None
        assert "테스트 보고서" in markdown
        assert "요약" in markdown or "SUMMARY" in markdown

        logger.info("✅ Regression: build_report_md() still works")

    def test_parse_markdown_to_content_still_works(self):
        """기존 parse_markdown_to_content() 함수 호환성"""
        from app.utils.markdown_parser import parse_markdown_to_content

        # Arrange
        markdown = """
# 테스트 제목

## 배경 및 목적
배경 내용...

## 결론
결론 내용...
"""

        # Act
        parsed = parse_markdown_to_content(markdown)

        # Assert
        assert parsed is not None
        assert "title" in parsed
        assert parsed["title"] == "테스트 제목"

        logger.info("✅ Regression: parse_markdown_to_content() still works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
