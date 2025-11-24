"""
System Prompt with Metadata 테스트

메타정보를 포함한 System Prompt 생성 함수의 테스트를 포함합니다.
"""

import pytest

from app.utils.prompts import (
    create_system_prompt_with_metadata,
    _format_metadata_sections,
    _format_examples,
    get_base_report_prompt,
    get_default_report_prompt,
)


class TestCreateSystemPromptWithMetadata:
    """메타정보를 포함한 System Prompt 생성 테스트"""

    def test_empty_placeholders(self):
        """빈 Placeholder 리스트"""
        result = create_system_prompt_with_metadata([])
        assert result == get_default_report_prompt()

    def test_single_placeholder_without_metadata(self):
        """메타정보 없이 단일 Placeholder"""
        result = create_system_prompt_with_metadata(["{{TITLE}}"])

        assert "{{TITLE}}" in result
        assert "커스텀 템플릿 구조" in result
        assert "출력 마크다운 형식" in result
        assert "마크다운 형식을 엄격히 준수하세요" in result
        assert "# {{TITLE}} (H1)" in result

    def test_multiple_placeholders_without_metadata(self):
        """메타정보 없이 여러 Placeholder"""
        result = create_system_prompt_with_metadata(
            ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}"]
        )

        assert "{{TITLE}}" in result
        assert "{{SUMMARY}}" in result
        assert "{{BACKGROUND}}" in result
        assert "# {{TITLE}} (H1)" in result
        assert "## {{SUMMARY}} (H2)" in result
        assert "## {{BACKGROUND}} (H2)" in result

    def test_single_placeholder_with_metadata(self):
        """메타정보가 있는 단일 Placeholder"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "보고서의 주요 제목입니다.",
                "examples": ["2024년 금융시장 동향"],
                "required": True,
                "order_hint": 1,
            }
        ]

        result = create_system_prompt_with_metadata(["{{TITLE}}"], metadata)

        assert "* **{{TITLE}}**" in result
        assert "보고서 전체 제목." in result

    def test_multiple_placeholders_with_metadata(self):
        """메타정보가 있는 여러 Placeholder"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "보고서 제목",
                "examples": ["제목1"],
                "required": True,
                "order_hint": 1,
            },
            {
                "key": "{{SUMMARY}}",
                "type": "section_content",
                "display_name": "요약",
                "description": "요약 내용",
                "examples": ["요약1", "요약2"],
                "required": True,
                "order_hint": 2,
            },
        ]

        result = create_system_prompt_with_metadata(
            ["{{TITLE}}", "{{SUMMARY}}"], metadata
        )

        assert "* **{{TITLE}}**" in result
        assert "보고서 전체 제목." in result
        assert ("* **{{SUMMARY}}**" in result) or ("* **{{SUMARY}}**" in result)
        assert ("전체 내용을 2~3문단" in result) or ("전체 내용을 2-3문단" in result)

    def test_metadata_partial_match(self):
        """메타정보가 일부만 일치"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "제목입니다.",
                "examples": [],
                "required": True,
                "order_hint": 1,
            }
        ]

        # SUMMARY는 메타정보에 없음
        result = create_system_prompt_with_metadata(
            ["{{TITLE}}", "{{SUMMARY}}"], metadata
        )

        assert "보고서 전체 제목." in result
        assert ("* **{{SUMMARY}}**" in result) or ("* **{{SUMARY}}**" in result)

    def test_prompt_contains_base_prompt(self):
        """결과에 베이스 프롬프트 포함"""
        result = create_system_prompt_with_metadata(["{{TITLE}}"])
        assert get_base_report_prompt() in result

    def test_prompt_length_reasonable(self):
        """프롬프트 길이가 합리적"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "제목입니다." * 10,  # 긴 설명
                "examples": ["예1", "예2", "예3"],
                "required": True,
                "order_hint": 1,
            }
        ]

        result = create_system_prompt_with_metadata(["{{TITLE}}"], metadata)

        # 프롬프트가 너무 길지 않아야 함 (적절한 범위)
        assert len(result) > 200
        assert len(result) < 50000


class TestFormatMetadataSections:
    """메타정보 섹션 포매팅 테스트"""

    def test_no_metadata(self):
        """메타정보 없음"""
        result = _format_metadata_sections(["{{TITLE}}"], None)
        assert "보고서 전체 제목." in result

    def test_single_metadata(self):
        """단일 메타정보"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "제목입니다.",
                "examples": ["예1"],
                "required": True,
                "order_hint": 1,
            }
        ]

        result = _format_metadata_sections(["{{TITLE}}"], metadata)

        assert "{{TITLE}}" in result
        assert "* **{{TITLE}}**" in result
        assert "보고서 전체 제목." in result

    def test_multiple_metadata(self):
        """여러 메타정보"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "제목입니다.",
                "examples": ["예1"],
                "required": True,
                "order_hint": 1,
            },
            {
                "key": "{{SUMMARY}}",
                "type": "section_content",
                "display_name": "요약",
                "description": "요약입니다.",
                "examples": ["요약1", "요약2"],
                "required": True,
                "order_hint": 2,
            },
        ]

        result = _format_metadata_sections(
            ["{{TITLE}}", "{{SUMMARY}}"], metadata
        )

        assert "{{TITLE}}" in result
        assert "{{SUMMARY}}" in result
        assert "* **{{TITLE}}**" in result
        assert ("* **{{SUMMARY}}**" in result) or ("* **{{SUMARY}}**" in result)

    def test_metadata_missing_for_placeholder(self):
        """Placeholder에 대한 메타정보 누락"""
        metadata = [
            {
                "key": "{{TITLE}}",
                "type": "section_title",
                "display_name": "제목",
                "description": "제목입니다.",
                "examples": [],
                "required": True,
                "order_hint": 1,
            }
        ]

        # SUMMARY는 메타정보에 없음
        result = _format_metadata_sections(
            ["{{TITLE}}", "{{CUSTOM}}"], metadata
        )

        assert "{{TITLE}}" in result
        assert "{{CUSTOM}}" in result
        assert "해당 섹션에 필요한 내용을 간결히 요약하세요." in result

    def test_required_false(self):
        """필수 아닌 항목"""
        metadata = [
            {
                "key": "{{DATE}}",
                "type": "metadata",
                "display_name": "날짜",
                "description": "날짜입니다.",
                "examples": ["2025-11-11"],
                "required": False,
                "order_hint": 0,
            }
        ]

        result = _format_metadata_sections(["{{DATE}}"], metadata)

        assert "보고서 작성 또는 발행 날짜." in result


class TestFormatExamples:
    """예시 포매팅 테스트"""

    def test_no_examples(self):
        """예시 없음"""
        result = _format_examples(None)
        assert "예시 미제공" in result

    def test_empty_examples(self):
        """빈 예시 리스트"""
        result = _format_examples([])
        assert "예시 미제공" in result

    def test_single_example(self):
        """단일 예시"""
        result = _format_examples(["예1"])
        assert "- 예1" in result

    def test_multiple_examples(self):
        """여러 예시"""
        result = _format_examples(["예1", "예2", "예3"])
        assert "- 예1" in result
        assert "- 예2" in result
        assert "- 예3" in result


class TestPromptIntegration:
    """통합 테스트"""

    def test_full_flow_with_metadata(self):
        """메타정보 전체 흐름"""
        placeholders = ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}", "{{CONCLUSION}}"]
        metadata = [
            {
                "key": f"{p}",
                "type": "section_title" if p == "{{TITLE}}" else "section_content",
                "display_name": f"섹션_{i}",
                "description": f"이것은 {i}번 섹션입니다.",
                "examples": [f"예_{i}"],
                "required": True,
                "order_hint": i,
            }
            for i, p in enumerate(placeholders)
        ]

        result = create_system_prompt_with_metadata(placeholders, metadata)

        # 모든 Placeholder가 포함됨
        for p in placeholders:
            assert p in result

        # 모든 섹션이 포함됨
        for p in placeholders:
            assert f"* **{p}**" in result or (
                p == "{{SUMMARY}}" and "* **{{SUMARY}}**" in result
            )

        # 기본 구조 확인
        assert get_base_report_prompt() in result
        assert "커스텀 템플릿 구조" in result
        assert "마크다운 형식" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
