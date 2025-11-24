"""
Unit tests for sequential_planning with 2-step API calling.

Test Coverage:
- TC-FUNC-003: get_plan_markdown_rules() 반환
- TC-FUNC-004: 2단계 API 호출 검증
- TC-FUNC-005: JSON → 마크다운 변환
- TC-FUNC-006: prompt_system 반환
- TC-FUNC-007: 마크다운 형식 (first_response_md)
- TC-ERROR-011: 첫 번째 API 실패
- TC-ERROR-012: 두 번째 API 실패
- TC-ERROR-013: JSON 파싱 실패 (첫 번째)
- TC-ERROR-014: JSON 파싱 실패 (두 번째)
"""
import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from app.utils.prompts import get_plan_markdown_rules
from app.utils.sequential_planning import (
    sequential_planning,
    SequentialPlanningError,
    _build_prompt_user_from_first_response,
)


class TestGetPlanMarkdownRules:
    """get_plan_markdown_rules() 함수 테스트"""

    def test_get_plan_markdown_rules(self):
        """TC-FUNC-003: get_plan_markdown_rules() 반환"""
        rules = get_plan_markdown_rules()

        assert isinstance(rules, str)
        assert "BACKGROUND" in rules
        assert "MAIN_CONTENT" in rules
        assert "SUMMARY" in rules
        assert "CONCLUSION" in rules

    def test_plan_markdown_rules_format(self):
        """Markdown rules의 기본 구조 확인"""
        rules = get_plan_markdown_rules()

        assert "##" in rules  # Markdown H2 포함
        assert len(rules) > 100  # 충분한 길이


class TestTwoStepAPICalls:
    """2단계 API 호출 테스트"""

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_two_step_api_calls(self, mock_call):
        """TC-FUNC-004: 2단계 API 호출 검증"""
        # Mock responses
        first_response = json.dumps({
            "selected_role": "Financial Analyst",
            "framework": "Top-down",
            "sections": [
                {
                    "title": "배경",
                    "description": "금융 분석 배경",
                    "key_points": ["포인트1", "포인트2"],
                    "order": 1
                }
            ]
        })

        second_response = json.dumps({
            "title": "최종 계획",
            "sections": [
                {
                    "title": "배경",
                    "description": "최종 배경",
                    "key_points": [],
                    "order": 1
                }
            ]
        })

        mock_call.side_effect = [first_response, second_response]

        result = await sequential_planning(topic="AI 분석", is_template_used=False)

        # API 호출 2회 확인
        assert mock_call.call_count == 2

        # 반환값 검증
        assert "plan" in result
        assert "sections" in result
        assert "prompt_user" in result
        assert "prompt_system" in result

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_single_step_api_call(self, mock_call):
        """Single-step (is_template_used=True) API 호출 검증"""
        response = json.dumps({
            "title": "계획",
            "sections": [
                {
                    "title": "배경",
                    "description": "배경 설명",
                    "key_points": [],
                    "order": 1
                }
            ]
        })

        mock_call.return_value = response

        result = await sequential_planning(topic="AI 분석", is_template_used=True)

        # API 호출 1회 확인
        assert mock_call.call_count == 1

        # 반환값 검증 (prompt 필드 미포함)
        assert "plan" in result
        assert "sections" in result


class TestMarkdownConversion:
    """JSON → 마크다운 변환 테스트"""

    def test_markdown_conversion(self):
        """TC-FUNC-005: JSON → 마크다운 변환"""
        first_response = {
            "selected_role": "Financial Analyst",
            "framework": "Top-down Macro Analysis",
            "sections": [
                {
                    "title": "배경",
                    "description": "금융 분석 배경",
                    "key_points": ["포인트1", "포인트2"],
                    "order": 1
                }
            ]
        }

        result = _build_prompt_user_from_first_response(first_response)

        assert isinstance(result, str)
        assert "선택된 역할" in result
        assert "Financial Analyst" in result
        assert "프레임워크" in result
        assert "Top-down Macro Analysis" in result

    def test_markdown_conversion_includes_sections(self):
        """마크다운 변환 시 섹션 포함 확인"""
        first_response = {
            "selected_role": "Technical Architect",
            "framework": "System Design",
            "sections": [
                {
                    "title": "아키텍처",
                    "description": "시스템 아키텍처 설명",
                    "key_points": ["스케일", "안정성"],
                    "order": 1
                },
                {
                    "title": "구현",
                    "description": "구현 방안",
                    "key_points": ["모듈화"],
                    "order": 2
                }
            ]
        }

        result = _build_prompt_user_from_first_response(first_response)

        assert "섹션 1" in result
        assert "아키텍처" in result
        assert "섹션 2" in result
        assert "구현" in result
        assert "스케일" in result


class TestPromptSystemReturned:
    """prompt_system 반환 테스트"""

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_prompt_system_included(self, mock_call):
        """TC-FUNC-006: prompt_system 반환"""
        first_response = json.dumps({
            "selected_role": "Financial Analyst",
            "framework": "Top-down",
            "sections": []
        })

        second_response = json.dumps({
            "title": "계획",
            "sections": []
        })

        mock_call.side_effect = [first_response, second_response]

        result = await sequential_planning(topic="AI", is_template_used=False)

        assert "prompt_system" in result
        assert result["prompt_system"] == get_plan_markdown_rules()

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_single_step_no_prompt_system(self, mock_call):
        """Single-step에서 prompt_system 미포함"""
        response = json.dumps({
            "title": "계획",
            "sections": []
        })

        mock_call.return_value = response

        result = await sequential_planning(topic="AI", is_template_used=True)

        # Single-step에서는 prompt 필드 미포함
        assert "prompt_system" not in result
        assert "prompt_user" not in result


class TestErrorHandling:
    """에러 처리 테스트"""

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_first_api_failure(self, mock_call):
        """TC-ERROR-011: 첫 번째 API 실패"""
        mock_call.side_effect = Exception("API Error")

        with pytest.raises(SequentialPlanningError):
            await sequential_planning(topic="AI", is_template_used=False)

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_second_api_failure(self, mock_call):
        """TC-ERROR-012: 두 번째 API 실패"""
        first_response = json.dumps({
            "selected_role": "Analyst",
            "framework": "Framework",
            "sections": []
        })

        mock_call.side_effect = [first_response, Exception("Second API Error")]

        with pytest.raises(SequentialPlanningError):
            await sequential_planning(topic="AI", is_template_used=False)

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_first_json_parse_failure(self, mock_call):
        """TC-ERROR-013: 첫 번째 JSON 파싱 실패"""
        mock_call.side_effect = ["invalid json", '{"sections": []}']

        with pytest.raises(SequentialPlanningError):
            await sequential_planning(topic="AI", is_template_used=False)

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_second_json_parse_failure(self, mock_call):
        """TC-ERROR-014: 두 번째 JSON 파싱 실패"""
        first_response = json.dumps({
            "selected_role": "Analyst",
            "framework": "Framework",
            "sections": []
        })

        mock_call.side_effect = [first_response, "invalid json"]

        with pytest.raises(SequentialPlanningError):
            await sequential_planning(topic="AI", is_template_used=False)

    @pytest.mark.asyncio
    async def test_invalid_topic(self):
        """Invalid topic 검증"""
        with pytest.raises(ValueError):
            await sequential_planning(topic="")

    @pytest.mark.asyncio
    async def test_topic_too_long(self):
        """Topic 길이 초과 검증"""
        long_topic = "A" * 201

        with pytest.raises(ValueError):
            await sequential_planning(topic=long_topic)
