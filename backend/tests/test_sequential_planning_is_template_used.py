"""
Test sequential_planning module's is_template_used parameter

TC-FUNC-004: get_advanced_planner_prompt() - 7섹션 키워드 포함
TC-FUNC-005: get_advanced_planner_prompt() - JSON 응답 형식 명시
TC-FUNC-006: sequential_planning (기본값) - get_base_plan_prompt 호출
TC-FUNC-007: sequential_planning (템플릿) - is_template_used=True
TC-FUNC-008: sequential_planning (Planner) - is_template_used=False
TC-FUNC-009: _parse_plan_response - JSON 파싱 및 마크다운 변환
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.utils.sequential_planning import (
    sequential_planning,
    _parse_plan_response,
    SequentialPlanningError
)
from app.utils.prompts import get_advanced_planner_prompt, get_base_plan_prompt


class TestAdvancedPlannerPrompt:
    """Test suite for get_advanced_planner_prompt()"""

    def test_advanced_planner_prompt_structure(self):
        """TC-FUNC-004: get_advanced_planner_prompt() - 7섹션 키워드 포함"""
        # Given: Call get_advanced_planner_prompt()
        prompt = get_advanced_planner_prompt()

        # Then: Prompt contains all 7 section keywords
        assert "TITLE" in prompt or "제목" in prompt
        assert "DATE" in prompt or "날짜" in prompt
        assert "BACKGROUND" in prompt or "배경" in prompt
        assert "MAIN_CONTENT" in prompt or "주요" in prompt
        assert "SUMMARY" in prompt or "요약" in prompt
        assert "CONCLUSION" in prompt or "결론" in prompt
        assert "SYSTEM" in prompt or "시스템" in prompt or "개요" in prompt

    def test_advanced_planner_prompt_json_format(self):
        """TC-FUNC-005: get_advanced_planner_prompt() - JSON 응답 형식 명시"""
        # Given: Call get_advanced_planner_prompt()
        prompt = get_advanced_planner_prompt()

        # Then: Prompt mentions JSON response format
        assert "json" in prompt.lower() or "JSON" in prompt

    def test_advanced_planner_prompt_contains_user_topic_placeholder(self):
        """TC-FUNC-005 (variant): Prompt contains {{USER_TOPIC}} placeholder"""
        # Given: Call get_advanced_planner_prompt()
        prompt = get_advanced_planner_prompt()

        # Then: Prompt contains {{USER_TOPIC}} placeholder
        assert "{{USER_TOPIC}}" in prompt


class TestSequentialPlanningFunction:
    """Test suite for sequential_planning function"""

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning.get_base_plan_prompt")
    @patch("app.utils.sequential_planning.get_advanced_planner_prompt")
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_sequential_planning_default_uses_base_prompt(
        self, mock_call, mock_advanced, mock_base
    ):
        """TC-FUNC-006: sequential_planning (기본값) - get_base_plan_prompt 호출"""
        # Given: Mock functions
        mock_base.return_value = "BASE_PROMPT"
        mock_advanced.return_value = "ADVANCED_PROMPT"
        mock_call.return_value = '{"title": "test", "sections": [], "estimated_word_count": 1000}'

        # When: Call sequential_planning without is_template_used
        await sequential_planning(topic="AI 시장 분석")

        # Then: get_base_plan_prompt is called, get_advanced_planner_prompt is not
        mock_base.assert_called_once()
        mock_advanced.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning.get_base_plan_prompt")
    @patch("app.utils.sequential_planning.get_advanced_planner_prompt")
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_sequential_planning_template_used_true(
        self, mock_call, mock_advanced, mock_base
    ):
        """TC-FUNC-007: sequential_planning (템플릿) - is_template_used=True"""
        # Given: Mock functions
        mock_base.return_value = "BASE_PROMPT"
        mock_advanced.return_value = "ADVANCED_PROMPT"
        mock_call.return_value = '{"title": "test", "sections": [], "estimated_word_count": 1000}'

        # When: Call sequential_planning with is_template_used=True
        await sequential_planning(topic="디지털 뱅킹", is_template_used=True)

        # Then: get_base_plan_prompt is called
        mock_base.assert_called_once()
        mock_advanced.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning.get_base_plan_prompt")
    @patch("app.utils.sequential_planning.get_advanced_planner_prompt")
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_sequential_planning_advanced_planner(
        self, mock_call, mock_advanced, mock_base
    ):
        """TC-FUNC-008: sequential_planning (Planner) - is_template_used=False"""
        # Given: Mock functions
        mock_base.return_value = "BASE_PROMPT"
        mock_advanced.return_value = "ADVANCED_PROMPT with {{USER_TOPIC}}"
        mock_call.return_value = '{"title": "advanced test", "sections": [], "estimated_word_count": 2000}'

        # When: Call sequential_planning with is_template_used=False
        result = await sequential_planning(topic="AI 규제", is_template_used=False)

        # Then: get_advanced_planner_prompt is called, get_base_plan_prompt is not
        mock_advanced.assert_called_once()
        mock_base.assert_not_called()

        # And: Result contains plan and sections
        assert "plan" in result
        assert "sections" in result

    @pytest.mark.asyncio
    @patch("app.utils.sequential_planning.get_advanced_planner_prompt")
    @patch("app.utils.sequential_planning._call_sequential_planning")
    async def test_sequential_planning_replaces_user_topic_placeholder(
        self, mock_call, mock_advanced
    ):
        """TC-FUNC-008 (variant): {{USER_TOPIC}} placeholder is replaced"""
        # Given: Mock functions with placeholder
        mock_advanced.return_value = "Create plan for {{USER_TOPIC}}"
        mock_call.return_value = '{"title": "test", "sections": [], "estimated_word_count": 1000}'

        # When: Call sequential_planning with is_template_used=False
        await sequential_planning(topic="블록체인 기술", is_template_used=False)

        # Then: _call_sequential_planning receives prompt with topic replaced
        called_prompt = mock_call.call_args[0][0]
        assert "블록체인 기술" in called_prompt
        assert "{{USER_TOPIC}}" not in called_prompt


class TestParsePlanResponse:
    """Test suite for _parse_plan_response function"""

    def test_parse_plan_response_valid_json(self):
        """TC-FUNC-009: _parse_plan_response - JSON 파싱 및 마크다운 변환"""
        # Given: Valid JSON response
        json_response = """{
            "title": "AI 시장 분석 보고서",
            "sections": [
                {
                    "title": "개요",
                    "description": "AI 시장 개요",
                    "key_points": ["성장률", "시장 규모"],
                    "order": 1
                },
                {
                    "title": "주요 트렌드",
                    "description": "최신 트렌드 분석",
                    "key_points": ["생성형 AI", "자율주행"],
                    "order": 2
                }
            ],
            "estimated_word_count": 3000
        }"""

        # When: Parse response
        result = _parse_plan_response(json_response)

        # Then: Result contains plan and sections
        assert "plan" in result
        assert "sections" in result
        assert len(result["sections"]) == 2

        # And: Plan is markdown text
        plan_md = result["plan"]
        assert "AI 시장 분석 보고서" in plan_md
        assert "개요" in plan_md
        assert "주요 트렌드" in plan_md

    def test_parse_plan_response_json_with_markdown_code_block(self):
        """TC-FUNC-009 (variant): JSON wrapped in markdown code block"""
        # Given: JSON wrapped in ```json ... ```
        json_response = """```json
{
    "title": "테스트 계획",
    "sections": [
        {
            "title": "섹션1",
            "description": "설명",
            "key_points": ["포인트1"],
            "order": 1
        }
    ],
    "estimated_word_count": 1500
}
```"""

        # When: Parse response
        result = _parse_plan_response(json_response)

        # Then: Result is successfully parsed
        assert "plan" in result
        assert "sections" in result
        assert len(result["sections"]) == 1
        assert result["sections"][0]["title"] == "섹션1"

    def test_parse_plan_response_invalid_json(self):
        """TC-FUNC-009 (variant): Invalid JSON → SequentialPlanningError"""
        # Given: Invalid JSON response
        json_response = "{ invalid json"

        # Then: SequentialPlanningError is raised
        with pytest.raises(SequentialPlanningError) as exc_info:
            _parse_plan_response(json_response)

        assert "Failed to parse plan response" in str(exc_info.value)

    def test_parse_plan_response_empty_sections(self):
        """TC-FUNC-009 (variant): JSON with empty sections array"""
        # Given: JSON with no sections
        json_response = """{
            "title": "빈 계획",
            "sections": [],
            "estimated_word_count": 0
        }"""

        # When: Parse response
        result = _parse_plan_response(json_response)

        # Then: Result has empty sections array
        assert result["sections"] == []
        assert "빈 계획" in result["plan"]

    def test_parse_plan_response_outline_schema_mapping(self):
        """Call#2 bullet 아웃라인(JSON)도 기존 반환 형태로 변환된다"""
        outline_json = json.dumps({
            "TITLE": [
                "AI 시장 분석: 2025년 성장 동향, 경쟁 구도, 전략적 기회 평가",
                "생성형 AI에서 엔터프라이즈 AI까지 글로벌 시장의 현황과 미래",
            ],
            "DATE": ["2025년 11월 27일"],
            "BACKGROUND": ["시장 정의", "성장 배경"],
            "MAIN_CONTENT": ["세분화 분석", "경쟁 동향"],
            "SUMMARY": ["현 상태", "주요 기회"],
            "CONCLUSION": ["전략적 위상", "리스크"],
        })

        result = _parse_plan_response(outline_json)

        assert "plan" in result
        assert len(result["sections"]) == 6
        assert result["sections"][0]["title"] == "제목"
        assert result["sections"][0]["description"].startswith("AI 시장 분석")
        assert result["sections"][1]["title"] == "날짜"
        assert result["sections"][3]["title"] == "주요 내용"
        assert "세분화 분석" in result["sections"][3]["description"]

    def test_parse_plan_response_ignores_trailing_text(self):
        """JSON 뒤에 설명 텍스트가 이어져도 첫 JSON만 파싱한다"""
        raw = """{
  "TITLE": ["제목"],
  "DATE": ["2025-01-01"]
}

---

추가 설명이 이어집니다."""

        result = _parse_plan_response(raw)

        assert result["sections"][0]["title"] == "제목"


class TestSequentialPlanningValidation:
    """Test suite for sequential_planning input validation"""

    @pytest.mark.asyncio
    async def test_sequential_planning_empty_topic(self):
        """Test sequential_planning with empty topic → ValueError"""
        # Given: Empty topic
        # Then: ValueError is raised
        with pytest.raises(ValueError) as exc_info:
            await sequential_planning(topic="")

        assert "required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_sequential_planning_topic_too_long(self):
        """Test sequential_planning with topic > 200 chars → ValueError"""
        # Given: Topic exceeds 200 characters
        long_topic = "A" * 201

        # Then: ValueError is raised
        with pytest.raises(ValueError) as exc_info:
            await sequential_planning(topic=long_topic)

        assert "200" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sequential_planning_none_topic(self):
        """Test sequential_planning with None topic → ValueError"""
        # Given: None topic
        # Then: ValueError is raised
        with pytest.raises(ValueError) as exc_info:
            await sequential_planning(topic=None)

        assert "required" in str(exc_info.value).lower()
