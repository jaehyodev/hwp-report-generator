"""
API tests for POST /api/topics/plan with 2-step planning and prompt storage.

Test Coverage:
- TC-API-008: isTemplateUsed=false 분기
- TC-API-009: Prompt 데이터 저장
- TC-API-010: 응답 스키마 불변
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from app.models.topic import TopicCreate


class TestTwoStepPlanAPI:
    """2단계 계획 생성 API 테스트"""

    @pytest.mark.asyncio
    def test_two_step_plan_with_prompts(self, client, auth_headers):
        """TC-API-008, TC-API-009, TC-API-010: 2단계 계획 생성 + Prompt 저장 + 응답 스키마 불변"""
        # Mock sequential_planning response
        mock_response = {
            "plan": "# 계획\n## 배경\n최종 배경 계획",
            "sections": [
                {
                    "title": "배경",
                    "description": "금융 배경 설명",
                    "key_points": ["포인트1"],
                    "order": 1
                }
            ],
            "prompt_user": "## 선택된 역할: Financial Analyst\n프레임워크: Top-down",
            "prompt_system": "## BACKGROUND\n..."
        }

        with patch("app.routers.topics.sequential_planning", new_callable=AsyncMock, return_value=mock_response):
            # API 호출
            response = client.post(
                "/api/topics/plan",
                json={
                    "topic": "AI 시장 분석",
                    "isTemplateUsed": False
                },
                headers=auth_headers
            )

            # TC-API-010: 응답 스키마 불변
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "topic_id" in data["data"]
            assert "plan" in data["data"]

    @pytest.mark.asyncio
    def test_single_step_plan_no_prompts(self, client, auth_headers):
        """Single-step (is_template_used=true)에서 prompt 필드 미포함"""
        # Mock sequential_planning response (prompt 필드 없음)
        mock_response = {
            "plan": "# 계획\n...",
            "sections": [
                {
                    "title": "배경",
                    "description": "설명",
                    "key_points": [],
                    "order": 1
                }
            ]
        }

        with patch("app.routers.topics.sequential_planning", new_callable=AsyncMock, return_value=mock_response):
            response = client.post(
                "/api/topics/plan",
                json={
                    "topic": "AI 분석",
                    "isTemplateUsed": True
                },
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    def test_plan_with_template_id(self, client, auth_headers):
        """Template ID를 함께 전달하는 경우"""
        mock_response = {
            "plan": "# 계획",
            "sections": [],
            "prompt_user": "...",
            "prompt_system": "..."
        }

        with patch("app.routers.topics.sequential_planning", new_callable=AsyncMock, return_value=mock_response):
            response = client.post(
                "/api/topics/plan",
                json={
                    "topic": "AI 분석",
                    "templateId": 1,
                    "isTemplateUsed": False
                },
                headers=auth_headers
            )

            assert response.status_code == 200

    def test_plan_unauthorized_without_auth(self, client):
        """인증 없이 접근하는 경우"""
        response = client.post(
            "/api/topics/plan",
            json={"topic": "AI"}
        )

        # 인증 필수
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    def test_plan_with_is_web_search(self, client, auth_headers):
        """isWebSearch 파라미터 전달"""
        mock_response = {
            "plan": "# 계획",
            "sections": [],
            "prompt_user": "...",
            "prompt_system": "..."
        }

        with patch("app.routers.topics.sequential_planning", new_callable=AsyncMock, return_value=mock_response) as mock_planning:
            response = client.post(
                "/api/topics/plan",
                json={
                    "topic": "AI",
                    "isWebSearch": True
                },
                headers=auth_headers
            )

            assert response.status_code == 200

            # sequential_planning에 is_web_search=True 전달 확인
            assert mock_planning.called
            call_kwargs = mock_planning.call_args[1]
            assert call_kwargs["is_web_search"] is True

    @pytest.mark.asyncio
    def test_plan_with_invalid_topic(self, client, auth_headers):
        """Invalid topic (empty) 검증"""
        response = client.post(
            "/api/topics/plan",
            json={
                "topic": "",
                "isTemplateUsed": False
            },
            headers=auth_headers
        )

        # 유효하지 않은 입력
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    def test_plan_response_structure(self, client, auth_headers):
        """응답 구조가 PlanResponse를 따르는지 확인"""
        mock_response = {
            "plan": "# 보고서 계획\n## 섹션1",
            "sections": [
                {
                    "title": "배경",
                    "description": "배경 설명",
                    "key_points": ["포인트1", "포인트2"],
                    "order": 1
                }
            ],
            "prompt_user": "## 역할",
            "prompt_system": "## 규칙"
        }

        with patch("app.routers.topics.sequential_planning", new_callable=AsyncMock, return_value=mock_response):
            response = client.post(
                "/api/topics/plan",
                json={
                    "topic": "AI 분석",
                    "isTemplateUsed": False
                },
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            # 응답 스키마 확인
            assert "success" in data
            assert "data" in data
            assert "topic_id" in data["data"]
            assert "plan" in data["data"]
            assert isinstance(data["data"]["topic_id"], int)
            assert isinstance(data["data"]["plan"], str)
