"""
Test POST /api/topics/plan endpoint's is_template_used parameter

TC-API-010: 기본값 backward compatibility (isTemplateUsed 미포함)
TC-API-011: isTemplateUsed=true 명시
TC-API-012: isTemplateUsed=false 명시 (Role Planner)
TC-API-013: Validation 오류 (topic 누락)
TC-API-014: template_id 우선순위 (isTemplateUsed=false 시 무시)
TC-API-015: 응답 스키마 일관성

TC-ERROR-016: LLM 호출 실패 (503)
TC-ERROR-017: JSON 파싱 실패 (500)
TC-ERROR-018: 응답 시간 초과 (504)
"""
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from app.models.topic import PlanRequest


@pytest.mark.allow_topic_without_template
class TestTopicsPlanEndpoint:
    """Test suite for POST /api/topics/plan endpoint"""

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_default_backward_compatibility(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-API-010: 기본값 backward compatibility (isTemplateUsed 미포함)"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 계획\n## 개요",
            "sections": [
                {"title": "개요", "description": "설명", "order": 1}
            ]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 1})()

        # When: POST /plan without isTemplateUsed field
        response = client.post(
            "/api/topics/plan",
            json={"topic": "AI 시장 분석"},
            headers=auth_headers
        )

        # Then: Response is 200 OK
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["success"] is True
        assert "topic_id" in response_json["data"]
        assert "plan" in response_json["data"]

        # And: sequential_planning was called with is_template_used=True (default)
        assert mock_planning.call_args[1]["is_template_used"] is True

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_template_used_true(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-API-011: isTemplateUsed=true 명시"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 템플릿 기반 계획",
            "sections": [{"title": "섹션1", "description": "설명", "order": 1}]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 2})()

        # When: POST /plan with isTemplateUsed=true
        response = client.post(
            "/api/topics/plan",
            json={"topic": "디지털 뱅킹", "isTemplateUsed": True},
            headers=auth_headers
        )

        # Then: Response is 200 OK
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["success"] is True

        # And: sequential_planning was called with is_template_used=True
        assert mock_planning.call_args[1]["is_template_used"] is True

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_advanced_planner(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-API-012: isTemplateUsed=false 명시 (Role Planner)"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 고급 플래너 계획",
            "sections": [
                {"title": "개요", "description": "상세 설명", "order": 1},
                {"title": "주요내용", "description": "분석", "order": 2}
            ]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 3})()

        # When: POST /plan with isTemplateUsed=false
        response = client.post(
            "/api/topics/plan",
            json={"topic": "블록체인 기술", "isTemplateUsed": False},
            headers=auth_headers
        )

        # Then: Response is 200 OK
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["success"] is True
        assert "plan" in response_json["data"]

        # And: sequential_planning was called with is_template_used=False
        assert mock_planning.call_args[1]["is_template_used"] is False

    def test_plan_validation_topic_missing(self, client, auth_headers):
        """TC-API-013: Validation 오류 (topic 누락)"""
        # When: POST /plan without topic
        response = client.post(
            "/api/topics/plan",
            json={"isTemplateUsed": True},
            headers=auth_headers
        )

        # Then: Response is 422 Unprocessable Entity
        assert response.status_code == 422

    def test_plan_validation_topic_too_long(self, client, auth_headers):
        """TC-API-013 (variant): Validation 오류 (topic 길이 초과)"""
        # Given: Topic exceeds max_length (200)
        long_topic = "A" * 201

        # When: POST /plan with long topic
        response = client.post(
            "/api/topics/plan",
            json={"topic": long_topic},
            headers=auth_headers
        )

        # Then: Response is 422 Unprocessable Entity
        assert response.status_code == 422

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_template_id_ignored_when_not_used(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-API-014: template_id 우선순위 (isTemplateUsed=false 시 무시)"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 플래너 계획",
            "sections": [{"title": "섹션", "description": "설명", "order": 1}]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 4})()

        # When: POST /plan with template_id=99 but isTemplateUsed=false
        response = client.post(
            "/api/topics/plan",
            json={
                "topic": "ESG 투자",
                "template_id": 99,
                "isTemplateUsed": False
            },
            headers=auth_headers
        )

        # Then: Response is 200 OK
        assert response.status_code == 200

        # And: sequential_planning was called with is_template_used=False
        # (template_id should be ignored)
        assert mock_planning.call_args[1]["is_template_used"] is False

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_response_schema_consistency(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-API-015: 응답 스키마 일관성"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 테스트 계획\n## 섹션1\n내용",
            "sections": [
                {
                    "title": "섹션1",
                    "description": "섹션 설명",
                    "key_points": ["포인트1", "포인트2"],
                    "order": 1
                }
            ]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 5})()

        # When: POST /plan
        response = client.post(
            "/api/topics/plan",
            json={"topic": "금융 규제"},
            headers=auth_headers
        )

        # Then: Response has consistent schema
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["success"] is True

        data = response_json["data"]
        assert "topic_id" in data
        assert "plan" in data
        assert isinstance(data["topic_id"], int)
        assert isinstance(data["plan"], str)


@pytest.mark.allow_topic_without_template
class TestTopicsPlanErrorHandling:
    """Test suite for error handling in POST /api/topics/plan"""

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_llm_call_failure(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-ERROR-016: LLM 호출 실패 (500)"""
        # Given: sequential_planning raises exception
        from app.utils.sequential_planning import SequentialPlanningError
        mock_planning.side_effect = SequentialPlanningError("Claude API error")

        # When: POST /plan
        response = client.post(
            "/api/topics/plan",
            json={"topic": "AI 윤리"},
            headers=auth_headers
        )

        # Then: Response is 500 Internal Server Error
        assert response.status_code == 500
        response_json = response.json()
        assert response_json["success"] is False
        assert "error" in response_json

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_json_parsing_failure(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-ERROR-017: JSON 파싱 실패 (500)"""
        # Given: sequential_planning raises SequentialPlanningError (JSON parse)
        from app.utils.sequential_planning import SequentialPlanningError
        mock_planning.side_effect = SequentialPlanningError("Failed to parse plan response")

        # When: POST /plan
        response = client.post(
            "/api/topics/plan",
            json={"topic": "양자컴퓨팅"},
            headers=auth_headers
        )

        # Then: Response is 500 Internal Server Error
        assert response.status_code == 500
        response_json = response.json()
        assert response_json["success"] is False

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_timeout(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """TC-ERROR-018: 응답 시간 초과 (504)"""
        # Given: sequential_planning raises TimeoutError
        from app.utils.sequential_planning import TimeoutError
        mock_planning.side_effect = TimeoutError("Response time exceeded 2 seconds")

        # When: POST /plan
        response = client.post(
            "/api/topics/plan",
            json={"topic": "우주 탐사"},
            headers=auth_headers
        )

        # Then: Response is 504 Gateway Timeout
        assert response.status_code == 504
        response_json = response.json()
        assert response_json["success"] is False
        assert "error" in response_json


@pytest.mark.allow_topic_without_template
class TestTopicsPlanAuthentication:
    """Test suite for authentication in POST /api/topics/plan"""

    def test_plan_unauthorized(self, client):
        """Test POST /plan without authentication → 403"""
        # When: POST /plan without Authorization header
        response = client.post(
            "/api/topics/plan",
            json={"topic": "클라우드 컴퓨팅"}
        )

        # Then: Response is 403 Forbidden (FastAPI default for missing auth)
        assert response.status_code == 403


@pytest.mark.allow_topic_without_template
class TestTopicsPlanIntegration:
    """Integration tests for POST /api/topics/plan"""

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_with_web_search(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """Test POST /plan with isWebSearch=true"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 웹 검색 기반 계획",
            "sections": [{"title": "현황", "description": "최신 정보", "order": 1}]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 6})()

        # When: POST /plan with isWebSearch=true
        response = client.post(
            "/api/topics/plan",
            json={
                "topic": "최신 AI 트렌드",
                "isWebSearch": True,
                "isTemplateUsed": False
            },
            headers=auth_headers
        )

        # Then: Response is 200 OK
        assert response.status_code == 200

        # And: sequential_planning was called with is_web_search=True
        assert mock_planning.call_args[1]["is_web_search"] is True

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_plan_full_request(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """Test POST /plan with all parameters"""
        # Given: Mock functions
        mock_planning.return_value = {
            "plan": "# 완전한 계획\n## 전체 개요\n상세 내용",
            "sections": [
                {"title": "개요", "description": "전체 개요", "order": 1},
                {"title": "분석", "description": "상세 분석", "order": 2},
                {"title": "결론", "description": "최종 결론", "order": 3}
            ]
        }
        mock_create_topic.return_value = type('obj', (object,), {'id': 7})()

        # When: POST /plan with all parameters
        response = client.post(
            "/api/topics/plan",
            json={
                "topic": "종합 금융 전략",
                "template_id": 10,
                "isWebSearch": True,
                "isTemplateUsed": True
            },
            headers=auth_headers
        )

        # Then: Response is 200 OK with complete data
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["success"] is True

        data = response_json["data"]
        assert data["topic_id"] == 7
        assert "plan" in data
        assert "완전한 계획" in data["plan"]
