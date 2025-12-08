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
    _extract_prompt_fields,
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
        # 두 번째 호출의 system_prompt에 role/context가 포함되는지 확인
        _, second_kwargs = mock_call.call_args_list[1]
        assert "system_prompt" in second_kwargs
        assert "Financial Analyst" in second_kwargs["system_prompt"]
        assert "Top-down" in second_kwargs["system_prompt"]

        # 반환값 검증
        assert "plan" in result
        assert "sections" in result
        assert "prompt_user" in result
        assert "prompt_system" in result
        assert "Financial Analyst" in result["prompt_user"]
        assert "Top-down" in result["prompt_user"]
        assert "Financial Analyst" in result["prompt_system"]
        assert "Top-down" in result["prompt_system"]

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

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_two_step_missing_role_context_task_uses_defaults(self, mock_call):
        """role/context/task 누락 시 기본값으로 prompt_user/system을 구성"""
        first_response = json.dumps({
            "sections": [
                {"title": "A", "description": "desc", "key_points": [], "order": 1}
            ]
        })
        second_response = json.dumps({
            "title": "계획",
            "sections": []
        })

        mock_call.side_effect = [first_response, second_response]

        result = await sequential_planning(topic="AI", is_template_used=False)

        assert "전문가" in result["prompt_user"]
        assert "맥락 정보가 제공되지 않았습니다." in result["prompt_user"]
        assert "보고서 계획을 작성하세요" in result["prompt_user"]
        assert "전문가" in result["prompt_system"]
        assert "맥락 정보가 제공되지 않았습니다." in result["prompt_system"]



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
        assert "전문가" in result["prompt_system"]
        assert "맥락 정보가 제공되지 않았습니다." in result["prompt_system"]
        assert get_plan_markdown_rules() in result["prompt_system"]


class TestPromptFieldExtraction:
    """restructured_prompt JSON 매핑 테스트"""

    def test_extract_prompt_fields_from_restructured_prompt(self):
        """새 JSON 스키마(restructured_prompt/analysis)에서 role/context/task 추출"""
        first_response = {
            "analysis": {
                "hidden_intent": "의도",
                "primary_purpose": "목적"
            },
            "restructured_prompt": {
                "role": "시장 분석 전문가",
                "context": "급변하는 AI 시장",
                "task": "시장 분석 단계별 수행",
                "why": "비즈니스 전략 수립"
            }
        }

        fields = _extract_prompt_fields(first_response)

        assert fields["role"] == "시장 분석 전문가"
        assert fields["context"] == "급변하는 AI 시장"
        assert fields["task"] == "시장 분석 단계별 수행"

    def test_extract_prompt_fields_fallback_to_analysis_when_context_missing(self):
        """context가 비어 있을 때 analysis 정보를 사용해 보강"""
        first_response = {
            "analysis": {
                "hidden_intent": "시장 현황 파악",
                "primary_purpose": "투자 판단"
            },
            "restructured_prompt": {
                "role": "시장 분석 전문가",
                "task": "시장 분석 단계별 수행"
            }
        }

        fields = _extract_prompt_fields(first_response)

        assert "시장 현황 파악" in fields["context"]
        assert "투자 판단" in fields["context"]
        assert fields["role"] == "시장 분석 전문가"
        assert fields["task"] == "시장 분석 단계별 수행"

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
