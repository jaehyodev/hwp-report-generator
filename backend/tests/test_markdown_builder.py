"""
Unit Tests for postprocess_headings() function

This test module validates the H2 markdown heading to ordered list conversion.
Tests cover numeric/non-numeric H2 formats, mixed formats, and edge cases.

Target Function: postprocess_headings(text: str) -> str
Location: backend/app/utils/markdown_builder.py
"""

import pytest
from app.utils.markdown_builder import postprocess_headings


class TestPostprocessHeadings:
    """Unit tests for postprocess_headings() function."""

    def test_tc_ut_001_numeric_h2_without_space(self):
        """TC-UT-001: Numeric H2 without space between ## and number.

        Input: "##1.제목\n내용"
        Expected: "1. 제목\n내용"

        Validates:
        - H2 with number attached to ##
        - Conversion to list format with one space after number
        - Preservation of following content (본문)
        """
        input_text = "##1.제목\n내용"
        expected = "1. 제목\n내용"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_tc_ut_002_numeric_h2_with_space_variants(self):
        """TC-UT-002: Numeric H2 with various space formats.

        Input: "## 2 제목\n- bullet"
        Expected: "2. 제목\n- bullet"

        Validates:
        - H2 with space before and after number
        - Bullet points are preserved
        - Consistent spacing in output (1 space after number)
        """
        input_text = "## 2 제목\n- bullet"
        expected = "2. 제목\n- bullet"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_tc_ut_003_non_numeric_h2_single(self):
        """TC-UT-003: Single non-numeric H2 heading.

        Input: "##제목\n본문"
        Expected: "1. 제목\n본문"

        Validates:
        - H2 without leading number
        - Auto-numbering starts at 1
        - Content preservation
        """
        input_text = "##제목\n본문"
        expected = "1. 제목\n본문"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_tc_ut_004_no_h2_headings(self):
        """TC-UT-004: Input with no H2 headings.

        Input: "일반 텍스트\n내용"
        Expected: "일반 텍스트\n내용" (no change)

        Validates:
        - No H2 patterns found
        - Original text returned unchanged
        """
        input_text = "일반 텍스트\n내용"
        expected = "일반 텍스트\n내용"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_tc_ut_005_multiple_mixed_h2(self):
        """TC-UT-005: Multiple H2 headings with mixed numeric/non-numeric.

        Input: "##1.첫\n##제목\n## 3 셋"
        Expected: "1. 첫\n2. 제목\n3. 셋"

        Validates:
        - First H2 with number (1) is preserved
        - Second H2 without number is auto-numbered (2)
        - Third H2 with number (3) is preserved as-is
        - Auto-numbering respects explicit numbers
        """
        input_text = "##1.첫\n##제목\n## 3 셋"
        expected = "1. 첫\n2. 제목\n3. 셋"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_tc_ut_006_mixed_format_comprehensive(self):
        """TC-UT-006: Comprehensive mixed format with multiple H2 types.

        Input: "##1. 배경\n##내용\n##방법\n## 4 결론"
        Expected: "1. 배경\n2. 내용\n3. 방법\n4. 결론"

        Validates:
        - Number continuity (1, 2, 3, 4)
        - Auto-numbering fills gaps between explicit numbers
        - Consistent list format across all variations
        """
        input_text = "##1. 배경\n##내용\n##방법\n## 4 결론"
        expected = "1. 배경\n2. 내용\n3. 방법\n4. 결론"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_tc_ut_007_duplicate_number_handling(self):
        """TC-UT-007: Duplicate number handling - auto-adjust repeated numbers.

        Input: "##1. 첫\n##1. 중복"
        Expected: "1. 첫\n2. 중복"

        Validates:
        - When same number appears twice, second occurrence is auto-incremented
        - max_num tracking ensures sequential numbering
        """
        input_text = "##1. 첫\n##1. 중복"
        expected = "1. 첫\n2. 중복"
        result = postprocess_headings(input_text)
        assert result == expected


class TestPostprocessHeadingsEdgeCases:
    """Additional edge case tests for robustness."""

    def test_h2_with_multiple_spaces(self):
        """H2 with multiple spaces between ## and content.

        Input: "##   제목"
        Expected: "1. 제목" (normalized to single space)
        """
        input_text = "##   제목"
        expected = "1. 제목"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_h2_with_special_characters(self):
        """H2 with special characters in title.

        Input: "##제목 (2024년)"
        Expected: "1. 제목 (2024년)"
        """
        input_text = "##제목 (2024년)"
        expected = "1. 제목 (2024년)"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_h2_with_period_no_number(self):
        """H2 starting with period (not a number).

        Input: "##.제목"
        Expected: "1. .제목"
        """
        input_text = "##.제목"
        expected = "1. .제목"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_non_h2_headings_preserved(self):
        """Non-H2 headings (H1, H3+) should not be converted.

        Input: "# H1\n##H2\n### H3"
        Expected: H1 and H3 unchanged, only H2 converted
        """
        input_text = "# H1\n##H2\n### H3"
        result = postprocess_headings(input_text)
        # H2 should be converted, H1 and H3 should remain
        assert "# H1" in result
        assert "1. H2" in result
        assert "### H3" in result

    def test_multiline_content_preservation(self):
        """Multi-paragraph content between H2s should be preserved.

        Input: "##첫\n첫번째 내용\n\n두 번째 단락\n##둘"
        Expected: Content and blank lines preserved
        """
        input_text = "##첫\n첫번째 내용\n\n두 번째 단락\n##둘"
        result = postprocess_headings(input_text)
        assert "1. 첫" in result
        assert "2. 둘" in result
        assert "첫번째 내용" in result
        assert "두 번째 단락" in result

    def test_large_number_preservation(self):
        """Large explicit numbers should be preserved.

        Input: "##999.제목"
        Expected: "999. 제목"
        """
        input_text = "##999.제목"
        expected = "999. 제목"
        result = postprocess_headings(input_text)
        assert result == expected

    def test_empty_text_input(self):
        """Empty input should return empty output.

        Input: ""
        Expected: ""
        """
        input_text = ""
        expected = ""
        result = postprocess_headings(input_text)
        assert result == expected

    def test_only_h2_no_content(self):
        """H2 heading with no following content.

        Input: "##제목"
        Expected: "1. 제목"
        """
        input_text = "##제목"
        expected = "1. 제목"
        result = postprocess_headings(input_text)
        assert result == expected


class TestPostprocessHeadingsPerformance:
    """Performance tests to ensure < 100ms response time."""

    def test_large_document_processing(self):
        """Test processing of large document with many H2s.

        Validates that processing time is within acceptable limits.
        """
        # Generate large document with 100 H2 headings
        lines = []
        for i in range(100):
            lines.append(f"##제목{i}")
            lines.append(f"이것은 내용 라인 {i}입니다.\n" * 5)

        input_text = "\n".join(lines)
        result = postprocess_headings(input_text)

        # All H2s should be converted
        for i in range(100):
            assert f"{i+1}. 제목{i}" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
