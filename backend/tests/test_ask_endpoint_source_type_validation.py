"""
/api/topics/{topic_id}/ask 엔드포인트 source_type 기반 조건부 검증 테스트

Spec: backend/doc/specs/20251201_ask_endpoint_source_type_conditional_validation.md

테스트 케이스:
- TC-001: source_type='template' + template_id 있음 + prompt_system 있음 → 200 OK
- TC-002: source_type='template' + template_id 없음 → 400 TEMPLATE_NOT_FOUND
- TC-003: source_type='basic' + template_id 없음 + prompt_system 있음 → 200 OK
- TC-004: source_type='basic' + template_id 없음 + prompt_system 없음 → 400 VALIDATION_REQUIRED_FIELD
- TC-005: source_type='template' + template_id 있음 + prompt_system 없음 → 400 VALIDATION_REQUIRED_FIELD
- TC-006: source_type='basic' + template_id 있음 + prompt_system 있음 → 200 OK
- TC-007: source_type=None (기본값 'basic') + prompt_system 있음 → 200 OK
- TC-008: 기존 회귀 테스트
"""
import pytest
from unittest.mock import patch, MagicMock

from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.models.topic import TopicCreate
from app.models.message import MessageCreate
from shared.types.enums import TopicStatus, TopicSourceType, MessageRole, ArtifactKind


@pytest.mark.api
class TestAskSourceTypeConditionalValidation:
    """ask() 엔드포인트 source_type 기반 조건부 검증 테스트"""

    # ==================== TC-001 ====================
    def test_ask_template_type_with_template_id_and_prompt_system(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-001: source_type='template' + template_id 있음 + prompt_system 있음
        기대결과: 200 OK (정상 처리)
        """
        # 사전 데이터: 템플릿 타입 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=TopicSourceType.TEMPLATE,
                template_id=1,  # ✅ template_id 있음
                prompt_system="당신은 금융 분석가입니다..."  # ✅ prompt_system 있음
            )
        )

        # mock: Claude API 응답
        mock_response_text = """# 분석 결과

## 개요
분석 내용입니다."""

        with patch('app.routers.topics.ClaudeClient') as mock_claude:
            mock_client = MagicMock()
            mock_client.chat_completion.return_value = (mock_response_text, 100, 50)
            mock_claude.return_value = mock_client

            # 요청
            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"content": "이 주제에 대해 분석해주세요"}
            )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["assistant_message"] is not None

    # ==================== TC-002 ====================
    def test_ask_template_type_without_template_id(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-002: source_type='template' + template_id 없음
        기대결과: 400 Bad Request (TEMPLATE_NOT_FOUND)
        """
        # 사전 데이터: 템플릿 타입인데 template_id가 없는 토픽
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=TopicSourceType.TEMPLATE,
                template_id=None,  # ❌ template_id 없음 (잘못된 데이터)
                prompt_system="프롬프트..."
            )
        )

        # 요청
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "질문 내용"}
        )

        # 검증
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert "TEMPLATE_NOT_FOUND" in body["error_code"]
        assert "템플릿" in body["message"]

    # ==================== TC-003 ====================
    def test_ask_basic_type_without_template_id_with_prompt_system(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-003: source_type='basic' + template_id 없음 + prompt_system 있음
        기대결과: 200 OK (정상 처리, template_id 검증 스킵)
        """
        # 사전 데이터: 기본 타입 토픽 (template_id 없음)
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=TopicSourceType.BASIC,
                template_id=None,  # ✅ null 허용
                prompt_system="기본 금융 분석 프롬프트..."
            )
        )

        # mock: Claude API 응답
        mock_response_text = """# 기본 분석

## 결과
기본 분석 내용"""

        with patch('app.routers.topics.ClaudeClient') as mock_claude:
            mock_client = MagicMock()
            mock_client.chat_completion.return_value = (mock_response_text, 80, 40)
            mock_claude.return_value = mock_client

            # 요청
            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"content": "기본 분석을 해주세요"}
            )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["assistant_message"] is not None

    # ==================== TC-004 ====================
    def test_ask_basic_type_without_template_id_without_prompt_system(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-004: source_type='basic' + template_id 없음 + prompt_system 없음
        기대결과: 400 Bad Request (VALIDATION_REQUIRED_FIELD, prompt_system 필수)
        """
        # 사전 데이터: 기본 타입 토픽인데 prompt_system이 없음
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=TopicSourceType.BASIC,
                template_id=None,
                prompt_system=None  # ❌ prompt_system 없음 (필수 필드)
            )
        )

        # 요청
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "질문 내용"}
        )

        # 검증
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert "VALIDATION.REQUIRED_FIELD" in body["error_code"]
        assert "프롬프트" in body["message"]
        assert "계획을 먼저 생성" in body["hint"]

    # ==================== TC-005 ====================
    def test_ask_template_type_with_template_id_without_prompt_system(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-005: source_type='template' + template_id 있음 + prompt_system 없음
        기대결과: 400 Bad Request (VALIDATION_REQUIRED_FIELD, prompt_system 필수)

        Step 2는 통과하지만 Step 3에서 실패
        """
        # 사전 데이터: 템플릿 타입 토픽인데 prompt_system이 없음
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=TopicSourceType.TEMPLATE,
                template_id=1,  # ✅ template_id 있음 (Step 2 통과)
                prompt_system=None  # ❌ prompt_system 없음 (Step 3 실패)
            )
        )

        # 요청
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "질문 내용"}
        )

        # 검증
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert "VALIDATION.REQUIRED_FIELD" in body["error_code"]
        assert "프롬프트" in body["message"]

    # ==================== TC-006 ====================
    def test_ask_basic_type_with_template_id_and_prompt_system(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-006: source_type='basic' + template_id 있음 + prompt_system 있음
        기대결과: 200 OK (호환성, template_id 무시하고 prompt_system 사용)
        """
        # 사전 데이터: 기본 타입인데 template_id도 있는 경우
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=TopicSourceType.BASIC,
                template_id=1,  # 있지만 무시됨
                prompt_system="사용자 맞춤 프롬프트..."
            )
        )

        # mock: Claude API 응답
        mock_response_text = """# 맞춤 분석

## 결과
맞춤 분석 내용"""

        with patch('app.routers.topics.ClaudeClient') as mock_claude:
            mock_client = MagicMock()
            mock_client.chat_completion.return_value = (mock_response_text, 90, 45)
            mock_claude.return_value = mock_client

            # 요청
            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"content": "맞춤 분석을 해주세요"}
            )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["assistant_message"] is not None

    # ==================== TC-007 ====================
    def test_ask_source_type_none_default_to_basic(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-007: source_type=None (기본값 'basic' 적용)
        기대결과: 200 OK (template_id 검증 스킵, 'basic'으로 취급)
        """
        # 사전 데이터: source_type이 NULL인 토픽
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="분석 주제",
                language="ko",
                source_type=None,  # NULL → 'basic'으로 기본값 처리
                template_id=None,
                prompt_system="기본 프롬프트..."
            )
        )

        # mock: Claude API 응답
        mock_response_text = """# 분석

## 결과
분석 내용"""

        with patch('app.routers.topics.ClaudeClient') as mock_claude:
            mock_client = MagicMock()
            mock_client.chat_completion.return_value = (mock_response_text, 70, 35)
            mock_claude.return_value = mock_client

            # 요청
            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"content": "분석을 해주세요"}
            )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["assistant_message"] is not None

    # ==================== TC-008 ====================
    def test_ask_regression_existing_tests(
        self, client, auth_headers, create_test_user
    ):
        """
        TC-008: 기존 회귀 테스트
        기대결과: 기존 ask 테스트가 모두 통과 (breaking change 없음)

        기존 토픽들은 보통 source_type='template'을 가정하므로,
        template_id와 prompt_system이 있어야 함
        """
        # 사전 데이터: 기존 방식의 토픽 (source_type='template' 가정)
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="기존 방식의 분석",
                language="ko",
                source_type=TopicSourceType.TEMPLATE,
                template_id=1,
                prompt_system="기존 프롬프트..."
            )
        )

        # mock: Claude API 응답
        mock_response_text = """# 기존 방식 분석

## 결과
기존 방식 분석 내용"""

        with patch('app.routers.topics.ClaudeClient') as mock_claude:
            mock_client = MagicMock()
            mock_client.chat_completion.return_value = (mock_response_text, 100, 50)
            mock_claude.return_value = mock_client

            # 요청
            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"content": "기존 방식으로 분석해주세요"}
            )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["assistant_message"] is not None
        assert body["data"]["user_message"]["content"] == "기존 방식으로 분석해주세요"


@pytest.mark.api
class TestAskPromptSystemRequired:
    """prompt_system 필수 검증 심화 테스트"""

    def test_prompt_system_validation_with_various_source_types(
        self, client, auth_headers, create_test_user
    ):
        """
        prompt_system이 필수인지 여러 source_type에서 검증
        """
        test_cases = [
            (TopicSourceType.TEMPLATE, 1, None, 400),  # template 타입 + template_id 있음 + prompt_system 없음 → 400
            (TopicSourceType.BASIC, None, None, 400),  # basic 타입 + template_id 없음 + prompt_system 없음 → 400
            (TopicSourceType.BASIC, 1, None, 400),  # basic 타입 + template_id 있음 + prompt_system 없음 → 400
        ]

        for source_type, template_id, prompt_system, expected_status in test_cases:
            # 토픽 생성
            topic = TopicDB.create_topic(
                user_id=create_test_user.id,
                topic_data=TopicCreate(
                    input_prompt=f"테스트_{source_type}_{template_id}_{prompt_system}",
                    language="ko",
                    source_type=source_type,
                    template_id=template_id,
                    prompt_system=prompt_system
                )
            )

            # 요청
            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"content": "테스트 질문"}
            )

            # 검증
            assert response.status_code == expected_status, (
                f"source_type={source_type}, template_id={template_id}, "
                f"prompt_system={prompt_system} → expected {expected_status}, "
                f"got {response.status_code}"
            )

            if expected_status == 400:
                body = response.json()
                assert body["success"] is False
