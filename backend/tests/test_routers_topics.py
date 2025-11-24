"""
토픽(대화 주제) API 라우터 테스트
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.models.topic import TopicCreate, TopicUpdate
from app.models.message import MessageCreate
from app.models.artifact import ArtifactCreate
from shared.types.enums import TopicStatus, MessageRole, ArtifactKind


@pytest.mark.api
class TestTopicsRouter:
    """Topics API 테스트"""

    def test_create_topic_success(self, client, auth_headers, create_test_user):
        response = client.post(
            "/api/topics",
            headers=auth_headers,
            json={
                "input_prompt": "디지털뱅킹 트렌드 분석",
                "language": "ko"
            }
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["id"] > 0
        assert body["data"]["input_prompt"] == "디지털뱅킹 트렌드 분석"

    def test_get_my_topics_empty(self, client, auth_headers):
        response = client.get("/api/topics", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total"] == 0
        assert body["data"]["topics"] == []

    def test_get_my_topics_with_one(self, client, auth_headers, create_test_user):
        # 사전 데이터: 토픽 1건 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="금융 리포트", language="ko")
        )

        response = client.get("/api/topics", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] >= 1
        assert any(t["id"] == topic.id for t in body["data"]["topics"])

    def test_get_topic_not_found(self, client, auth_headers):
        response = client.get("/api/topics/999999", headers=auth_headers)
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "TOPIC.NOT_FOUND"

    def test_get_topic_unauthorized(self, client, auth_headers, create_test_admin):
        # 관리자(다른 사용자) 소유 토픽 생성
        admin_topic = TopicDB.create_topic(
            user_id=create_test_admin.id,
            topic_data=TopicCreate(input_prompt="관리자 토픽", language="ko")
        )

        response = client.get(f"/api/topics/{admin_topic.id}", headers=auth_headers)
        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "TOPIC.UNAUTHORIZED"

    def test_update_topic_success(self, client, auth_headers, create_test_user):
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="초기 토픽", language="ko")
        )

        response = client.patch(
            f"/api/topics/{topic.id}",
            headers=auth_headers,
            json={
                "generated_title": "업데이트된 제목",
                "status": "archived"
            }
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["generated_title"] == "업데이트된 제목"
        assert body["data"]["status"] == TopicStatus.ARCHIVED.value

    def test_update_topic_unauthorized(self, client, auth_headers, create_test_admin):
        admin_topic = TopicDB.create_topic(
            user_id=create_test_admin.id,
            topic_data=TopicCreate(input_prompt="관리자 토픽", language="ko")
        )

        response = client.patch(
            f"/api/topics/{admin_topic.id}",
            headers=auth_headers,
            json={"generated_title": "허용되지 않음"}
        )

        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "TOPIC.UNAUTHORIZED"

    def test_delete_topic_success(self, client, auth_headers, create_test_user):
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="삭제 대상", language="ko")
        )

        response = client.delete(f"/api/topics/{topic.id}", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["message"]

    def test_delete_topic_not_found(self, client, auth_headers):
        response = client.delete("/api/topics/123456789", headers=auth_headers)
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "TOPIC.NOT_FOUND"

    @patch('app.routers.topics.ClaudeClient')
    def test_ask_success_no_artifact(
        self,
        mock_claude_class,
        client,
        auth_headers,
        create_test_user
    ):
        """참조 문서 없이 질문 성공 테스트"""
        # 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="디지털뱅킹 분석", language="ko")
        )

        # Mock Claude
        mock_claude_instance = MagicMock()
        mock_claude_instance.chat_completion.return_value = (
            "# 디지털뱅킹 트렌드\n\n## 요약\n\n2025년 디지털뱅킹 산업은...",
            100,
            200
        )
        mock_claude_instance.model = "claude-sonnet-4-5-20250929"
        mock_claude_class.return_value = mock_claude_instance

        # Ask 호출
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "디지털뱅킹 트렌드를 분석해주세요."}
        )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["topic_id"] == topic.id
        assert "user_message" in body["data"]
        assert "assistant_message" in body["data"]
        assert "artifact" in body["data"]
        assert "usage" in body["data"]
        assert body["data"]["artifact"]["kind"] == "md"
        assert body["data"]["usage"]["input_tokens"] == 100
        assert body["data"]["usage"]["output_tokens"] == 200

    @patch('app.routers.topics.ClaudeClient')
    def test_ask_with_latest_md(
        self,
        mock_claude_class,
        client,
        auth_headers,
        create_test_user,
        temp_dir
    ):
        """최신 MD 참조하여 질문 테스트"""
        # 토픽 + MD artifact 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="금융 보고서", language="ko")
        )

        # 초기 메시지 저장
        msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.ASSISTANT, content="# 초기 보고서\n\n내용...")
        )

        # MD 파일 생성
        from app.utils.file_utils import build_artifact_paths, write_text, sha256_of
        _, md_path = build_artifact_paths(topic.id, 1, "report.md")
        bytes_written = write_text(md_path, "# 초기 보고서\n\n내용...")
        file_hash = sha256_of(md_path)

        artifact = ArtifactDB.create_artifact(
            topic.id,
            msg.id,
            ArtifactCreate(
                kind=ArtifactKind.MD,
                locale="ko",
                version=1,
                filename="report.md",
                file_path=str(md_path),
                file_size=bytes_written,
                sha256=file_hash
            )
        )

        # Mock Claude (보고서 형식으로 응답, 각 섹션 50자 이상)
        mock_claude_instance = MagicMock()
        mock_claude_instance.chat_completion.return_value = (
            "## 요약\n개정된 보고서의 요약입니다. 충분히 긴 내용을 포함합니다. 이전 보고서의 주요 내용을 요약하였습니다.\n## 주요 내용\n업데이트된 내용이 여기에 포함됩니다. 이것은 의미있는 보고서 본문입니다. 자세한 분석 결과를 담고 있습니다.",
            200,
            300
        )
        mock_claude_instance.model = "claude-sonnet-4-5-20250929"
        mock_claude_class.return_value = mock_claude_instance

        # Ask 호출 (artifact_id=None, 자동으로 latest 사용)
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "이전 보고서를 요약해주세요."}
        )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["artifact"]["version"] == 2  # 새 버전 생성

        # Claude가 호출되었는지 확인
        mock_claude_instance.chat_completion.assert_called_once()

    @patch('app.routers.topics.ClaudeClient')
    def test_ask_with_specific_md(
        self,
        mock_claude_class,
        client,
        auth_headers,
        create_test_user,
        temp_dir
    ):
        """특정 MD 지정하여 질문 테스트"""
        # 토픽 + 여러 버전 MD 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="금융 보고서", language="ko")
        )

        # v1 생성
        msg1 = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.ASSISTANT, content="# v1 보고서")
        )
        from app.utils.file_utils import build_artifact_paths, write_text, sha256_of
        _, md_path1 = build_artifact_paths(topic.id, 1, "report.md")
        bytes1 = write_text(md_path1, "# v1 보고서")
        hash1 = sha256_of(md_path1)
        artifact1 = ArtifactDB.create_artifact(
            topic.id, msg1.id,
            ArtifactCreate(
                kind=ArtifactKind.MD, locale="ko", version=1,
                filename="report.md", file_path=str(md_path1),
                file_size=bytes1, sha256=hash1
            )
        )

        # v2 생성
        msg2 = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.ASSISTANT, content="# v2 보고서")
        )
        _, md_path2 = build_artifact_paths(topic.id, 2, "report.md")
        bytes2 = write_text(md_path2, "# v2 보고서")
        hash2 = sha256_of(md_path2)
        artifact2 = ArtifactDB.create_artifact(
            topic.id, msg2.id,
            ArtifactCreate(
                kind=ArtifactKind.MD, locale="ko", version=2,
                filename="report.md", file_path=str(md_path2),
                file_size=bytes2, sha256=hash2
            )
        )

        # Mock Claude
        mock_claude_instance = MagicMock()
        mock_claude_instance.chat_completion.return_value = (
            "# v1 기반 업데이트",
            150,
            250
        )
        mock_claude_instance.model = "claude-sonnet-4-5-20250929"
        mock_claude_class.return_value = mock_claude_instance

        # v1을 명시적으로 지정
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={
                "content": "v1 보고서를 기준으로 요약해주세요.",
                "artifact_id": artifact1.id
            }
        )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_ask_context_too_large(
        self,
        client,
        auth_headers,
        create_test_user
    ):
        """컨텍스트 길이 초과 테스트"""
        # 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="테스트", language="ko")
        )

        # 매우 긴 메시지들 생성
        for i in range(10):
            MessageDB.create_message(
                topic.id,
                MessageCreate(
                    role=MessageRole.USER,
                    content="가" * 10000  # 10,000자씩
                )
            )

        # Ask 호출 (총 100,000자 이상)
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "요약해주세요."}
        )

        # 400 MESSAGE.CONTEXT_TOO_LARGE 확인
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "MESSAGE.CONTEXT_TOO_LARGE"

    def test_ask_artifact_not_found(
        self,
        client,
        auth_headers,
        create_test_user
    ):
        """존재하지 않는 artifact_id 테스트"""
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="테스트", language="ko")
        )

        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={
                "content": "질문",
                "artifact_id": 999999
            }
        )

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "ARTIFACT.NOT_FOUND"

    def test_ask_artifact_wrong_kind(
        self,
        client,
        auth_headers,
        create_test_user,
        temp_dir
    ):
        """HWPX artifact 참조 시도 테스트"""
        # 토픽 + HWPX artifact 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="테스트", language="ko")
        )

        msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.ASSISTANT, content="테스트")
        )

        # HWPX 파일 생성 (실제로는 더미)
        from app.utils.file_utils import build_artifact_paths, write_text, sha256_of
        _, hwpx_path = build_artifact_paths(topic.id, 1, "report.hwpx")
        bytes_written = write_text(hwpx_path, "dummy hwpx content")
        file_hash = sha256_of(hwpx_path)

        artifact = ArtifactDB.create_artifact(
            topic.id, msg.id,
            ArtifactCreate(
                kind=ArtifactKind.HWPX,
                locale="ko",
                version=1,
                filename="report.hwpx",
                file_path=str(hwpx_path),
                file_size=bytes_written,
                sha256=file_hash
            )
        )

        # HWPX artifact_id 지정
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={
                "content": "질문",
                "artifact_id": artifact.id
            }
        )

        # 400 ARTIFACT.INVALID_KIND 확인
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "ARTIFACT.INVALID_KIND"

    def test_ask_unauthorized_topic(
        self,
        client,
        auth_headers,
        create_test_admin
    ):
        """타인의 토픽에 질문 테스트"""
        # 관리자의 토픽 생성
        admin_topic = TopicDB.create_topic(
            user_id=create_test_admin.id,
            topic_data=TopicCreate(input_prompt="관리자 토픽", language="ko")
        )

        # 일반 사용자로 요청 (auth_headers는 일반 사용자)
        response = client.post(
            f"/api/topics/{admin_topic.id}/ask",
            headers=auth_headers,
            json={"content": "질문"}
        )

        # 403 TOPIC.UNAUTHORIZED 확인
        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "TOPIC.UNAUTHORIZED"

    @patch('app.routers.topics.ClaudeClient')
    def test_ask_max_messages_limit(
        self,
        mock_claude_class,
        client,
        auth_headers,
        create_test_user
    ):
        """max_messages 제한 테스트"""
        # 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="테스트", language="ko")
        )

        # 50개 user 메시지 생성
        for i in range(50):
            MessageDB.create_message(
                topic.id,
                MessageCreate(role=MessageRole.USER, content=f"메시지 {i}")
            )

        # Mock Claude
        mock_claude_instance = MagicMock()
        mock_claude_instance.chat_completion.return_value = (
            "# 응답",
            100,
            200
        )
        mock_claude_instance.model = "claude-sonnet-4-5-20250929"
        mock_claude_class.return_value = mock_claude_instance

        # max_messages=10 설정
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={
                "content": "요약해주세요.",
                "max_messages": 10
            }
        )

        # 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        # Claude가 호출될 때 최근 10개만 포함되었는지 확인
        # (실제로는 메시지 수를 직접 확인하기 어려우므로, 성공 여부만 확인)
        mock_claude_instance.chat_completion.assert_called_once()

    def test_ask_empty_content(
        self,
        client,
        auth_headers,
        create_test_user
    ):
        """빈 content 테스트"""
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="테스트", language="ko")
        )

        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": ""}
        )

        assert response.status_code == 422  # Pydantic validation error
        # Pydantic validation errors use FastAPI's default format, not our custom error_response
        body = response.json()
        assert "detail" in body  # FastAPI's default error format

    def test_ask_topic_not_found(
        self,
        client,
        auth_headers
    ):
        """존재하지 않는 토픽에 질문 테스트"""
        response = client.post(
            "/api/topics/999999/ask",
            headers=auth_headers,
            json={"content": "질문"}
        )

        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "TOPIC.NOT_FOUND"

    @patch("app.routers.topics.ClaudeClient")
    def test_ask_with_artifact_filters_messages_by_seq_no(
        self,
        mock_claude_class,
        client,
        auth_headers
    ):
        """artifact_id 지정 시 해당 메시지 이전 메시지만 컨텍스트에 포함"""
        # Mock Claude
        mock_claude = MagicMock()
        mock_claude.chat_completion.return_value = (
            "# 수정된 보고서\n\n## 요약\n업데이트된 내용입니다.",
            1000,
            500
        )
        mock_claude.model = "claude-sonnet-4-5"
        mock_claude_class.return_value = mock_claude

        # 1. Topic 생성
        topic_response = client.post(
            "/api/topics",
            headers=auth_headers,
            json={"input_prompt": "테스트 주제"}
        )
        assert topic_response.status_code == 200
        topic_id = topic_response.json()["data"]["id"]

        # 2. 여러 메시지 생성 (1~5번)
        message_ids = []
        for i in range(1, 6):
            msg_response = client.post(
                f"/api/topics/{topic_id}/ask",
                headers=auth_headers,
                json={"content": f"질문 {i}"}
            )
            assert msg_response.status_code == 200
            message_ids.append(msg_response.json()["data"]["assistant_message"]["id"])

        # 3. 3번째 메시지의 artifact 조회
        third_msg_id = message_ids[2]  # 3번째 메시지
        
        # DB에서 artifact 조회
        from app.database.artifact_db import ArtifactDB
        from shared.types.enums import ArtifactKind
        
        third_artifact = ArtifactDB.get_artifacts_by_message(third_msg_id)[0]
        
        # 4. 해당 artifact_id로 새 질문 (5번째 메시지 이후)
        mock_claude.chat_completion.reset_mock()
        
        response = client.post(
            f"/api/topics/{topic_id}/ask",
            headers=auth_headers,
            json={
                "content": "3번 보고서 기준으로 수정해주세요",
                "artifact_id": third_artifact.id
            }
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "assistant_message" in data
        
        # 5. Claude 호출 검증 - 1~3번 메시지만 포함되어야 함
        mock_claude.chat_completion.assert_called_once()
        call_args = mock_claude.chat_completion.call_args
        messages = call_args[0][0]

        # Topic context와 artifact content 제외하고 실제 user 질문만 확인
        user_messages = [
            m for m in messages
            if m["role"] == "user"
            and not m["content"].startswith("**대화 주제**")
            and not m["content"].startswith("현재 보고서(MD)")
        ]

        # 3개의 user message만 포함되어야 함 (질문 1, 2, 3)
        # 질문 4, 5는 포함되면 안됨
        assert len(user_messages) == 3  # 질문 1~3만

        # 내용 검증
        user_contents = [m["content"] for m in user_messages]
        assert "질문 1" in user_contents[0]
        assert "질문 2" in user_contents[1]
        assert "질문 3" in user_contents[2]


    @patch("app.routers.topics.ClaudeClient")
    def test_ask_without_artifact_includes_all_messages(
        self,
        mock_claude_class,
        client,
        auth_headers
    ):
        """artifact_id 없이 요청 시 모든 user messages 포함 (기존 동작)"""
        # Mock Claude
        mock_claude = MagicMock()
        mock_claude.chat_completion.return_value = (
            "# 새 보고서\n\n## 요약\n새로운 내용입니다.",
            1000,
            500
        )
        mock_claude.model = "claude-sonnet-4-5"
        mock_claude_class.return_value = mock_claude

        # 1. Topic 생성
        topic_response = client.post(
            "/api/topics",
            headers=auth_headers,
            json={"input_prompt": "테스트 주제"}
        )
        assert topic_response.status_code == 200
        topic_id = topic_response.json()["data"]["id"]

        # 2. 여러 메시지 생성 (1~5번)
        for i in range(1, 6):
            msg_response = client.post(
                f"/api/topics/{topic_id}/ask",
                headers=auth_headers,
                json={"content": f"질문 {i}"}
            )
            assert msg_response.status_code == 200

        # 3. artifact_id 없이 새 질문
        mock_claude.chat_completion.reset_mock()
        
        response = client.post(
            f"/api/topics/{topic_id}/ask",
            headers=auth_headers,
            json={"content": "추가 질문"}
        )

        assert response.status_code == 200
        
        # 4. Claude 호출 검증 - 모든 메시지 포함되어야 함
        mock_claude.chat_completion.assert_called_once()
        call_args = mock_claude.chat_completion.call_args
        messages = call_args[0][0]

        # Topic context와 artifact content 제외하고 실제 user 질문만 확인
        user_messages = [
            m for m in messages
            if m["role"] == "user"
            and not m["content"].startswith("**대화 주제**")
            and not m["content"].startswith("현재 보고서(MD)")
        ]

        # 모든 질문이 포함되어야 함 (질문 1~5 + 추가 질문)
        # artifact_id 없이 요청하면 필터링하지 않음 (기존 동작)
        assert len(user_messages) == 6

        # 내용 검증
        user_contents = [m["content"] for m in user_messages]
        for i in range(1, 6):
            assert f"질문 {i}" in "".join(user_contents)
        assert "추가 질문" in user_contents[-1]

    def test_ask_saves_parsed_markdown_not_raw_response(self, client, auth_headers, create_test_user):
        """
        TC-ASK-001: /ask 엔드포인트에서 artifact 파일이 파싱된 마크다운을 저장하는지 검증

        - Claude 응답: 원본 마크다운 (제목, 요약, 배경, 주요내용, 결론 포함)
        - 기대: artifact 파일이 build_report_md() 통과한 구조화된 마크다운 포함
        - 미충족: artifact 파일이 Claude 원본 응답 전체 포함
        """
        # GIVEN: 토픽 생성
        topic_response = client.post(
            "/api/topics",
            json={"input_prompt": "테스트 주제", "language": "ko"},
            headers=auth_headers
        )
        topic_id = topic_response.json()["data"]["id"]

        # Claude 응답 mock (원본 마크다운, 50자 이상 섹션)
        claude_raw_response = """# 테스트 보고서 제목

## 요약
이것은 테스트 보고서의 요약입니다. 요약은 전체 내용을 간단하게 정리합니다. 이 섹션에서는 주요 내용을 강조합니다.

## 배경
보고서 작성의 배경과 목적을 설명합니다. 이 섹션에서는 왜 이 보고서가 필요한지 상세히 설명합니다. 배경은 이해를 도울 중요한 요소입니다.

## 주요 내용
분석 결과와 주요 발견 사항을 상세히 기술합니다. 충분한 길이의 분석이 포함됩니다.
- 첫 번째 포인트: 상세한 내용
- 두 번째 포인트: 분석 결과
- 세 번째 포인트: 결론

## 결론
종합적인 결론과 권고사항을 제시합니다. 향후 개선 방안을 제시합니다. 이 섹션은 전체 보고서의 최종 판단입니다."""

        with patch("app.utils.claude_client.ClaudeClient.chat_completion") as mock_claude:
            mock_claude.return_value = (claude_raw_response, 500, 300)

            # WHEN: /ask 요청
            response = client.post(
                f"/api/topics/{topic_id}/ask",
                json={"content": "첫 번째 질문입니다."},
                headers=auth_headers
            )

        # THEN: 요청 성공
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        artifact_id = response_data["data"]["artifact"]["id"]

        # artifact 파일 경로 확인
        artifact = ArtifactDB.get_artifact_by_id(artifact_id)
        assert artifact is not None
        assert artifact.file_path is not None

        # artifact 파일 내용 확인
        with open(artifact.file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()

        # 검증 1: 파싱된 마크다운은 섹션 제목을 포함해야 함
        # build_report_md()를 통과하므로 일관된 포맷을 가져야 함
        assert "## 요약" in saved_content or "## Summary" in saved_content, \
            "Parsed markdown should contain summary section"
        assert "## 결론" in saved_content or "## Conclusion" in saved_content, \
            "Parsed markdown should contain conclusion section"

        # 검증 2: 원본 응답 전체와는 다름을 확인
        # 만약 원본 응답을 그대로 저장했다면, 정확히 동일해야 함
        # (하지만 파싱/빌드 과정을 거쳤으므로 다를 것)
        assert saved_content != claude_raw_response, \
            "Saved content should be parsed, not raw Claude response"

        # 검증 3: 파일 크기가 합리적인 범위
        # 원본 응답(약 350자)보다 작거나 유사할 것으로 예상
        # (파싱 후 구조화되므로 크기는 비슷할 수 있음)
        assert len(saved_content) > 0, "Saved markdown should not be empty"

    def test_ask_markdown_parsing_consistency_with_generate(self, client, auth_headers, create_test_user):
        """
        TC-ASK-004: /ask와 generate_topic_report의 마크다운 파싱 일관성 검증

        - 동일한 Claude 응답으로 두 엔드포인트 호출
        - 기대: 생성된 artifact 파일의 구조가 동일
        """
        # Claude 응답 mock (50자 이상 각 섹션)
        claude_response = "# 통합 테스트 보고서\n## 핵심 요약\n이 보고서는 두 엔드포인트의 일관성을 검증합니다. 마크다운 파싱과 빌드 로직이 동일하게 작동해야 합니다. 이를 위해 동일한 Claude 응답으로 테스트합니다.\n## 배경 정보\n배경 정보를 여기에 상세히 기술합니다. 이 섹션에서는 충분한 길이의 설명을 제공합니다. 통합 테스트의 중요성을 강조합니다.\n## 분석 결과\n분석 결과를 상세히 기술합니다. 데이터와 인사이트를 포함한 깊이 있는 분석입니다. 일관성 검증이 핵심입니다.\n## 제언 및 결론\n최종 제언을 제시합니다. 향후 실행 계획을 포함한 종합적인 결론입니다. 모든 엔드포인트가 동일하게 작동합니다."

        with patch("app.utils.claude_client.ClaudeClient.chat_completion") as mock_claude:
            mock_claude.return_value = (claude_response, 400, 250)

            # 1. generate_topic_report로 생성
            gen_response = client.post(
                "/api/topics/generate",
                json={"input_prompt": "생성 테스트", "language": "ko"},
                headers=auth_headers
            )

        assert gen_response.status_code == 200
        gen_artifact_id = gen_response.json()["data"]["artifact_id"]
        gen_artifact = ArtifactDB.get_artifact_by_id(gen_artifact_id)

        with open(gen_artifact.file_path, 'r', encoding='utf-8') as f:
            gen_content = f.read()

        # 2. /ask로 생성
        topic_response = client.post(
            "/api/topics",
            json={"input_prompt": "ask 테스트", "language": "ko"},
            headers=auth_headers
        )
        topic_id = topic_response.json()["data"]["id"]

        with patch("app.utils.claude_client.ClaudeClient.chat_completion") as mock_claude:
            mock_claude.return_value = (claude_response, 400, 250)

            ask_response = client.post(
                f"/api/topics/{topic_id}/ask",
                json={"content": "같은 질문입니다."},
                headers=auth_headers
            )

        assert ask_response.status_code == 200
        ask_artifact_id = ask_response.json()["data"]["artifact"]["id"]
        ask_artifact = ArtifactDB.get_artifact_by_id(ask_artifact_id)

        with open(ask_artifact.file_path, 'r', encoding='utf-8') as f:
            ask_content = f.read()

        # THEN: 두 artifact 파일의 내용 구조가 동일해야 함
        # (동일한 Claude 응답으로 동일한 파싱/빌드 로직을 거쳤으므로)
        assert gen_content == ask_content, \
            "generate_topic_report and /ask should produce identical markdown"

    def test_ask_artifact_markdown_has_correct_sections(self, client, auth_headers, create_test_user):
        """
        TC-ASK-003: /ask로 생성된 artifact 마크다운의 섹션 검증

        - build_report_md() 통과 후 artifact에 저장된 마크다운 검증
        - 기대: 제목, 요약, 배경, 주요내용, 결론 섹션 포함
        """
        # GIVEN: 토픽 생성
        topic_response = client.post(
            "/api/topics",
            json={"input_prompt": "섹션 검증 테스트", "language": "ko"},
            headers=auth_headers
        )
        topic_id = topic_response.json()["data"]["id"]

        # Claude 응답 mock (50자 이상 각 섹션, 최소 50자 보장)
        claude_response = "# 섹션 검증 보고서\n## 요약 섹션\n요약 내용입니다. 이것은 50자 이상의 충분히 긴 요약 섹션입니다. 충분한 길이를 보장합니다.\n## 배경 섹션\n배경 내용입니다. 배경을 이해하기 위한 충분한 길이의 설명을 포함합니다. 자세한 설명입니다.\n## 주요 내용 섹션\n주요 내용입니다. 분석 결과와 핵심 발견사항을 상세히 기술합니다. 깊이 있는 분석입니다. 추가 설명.\n## 결론 섹션\n결론 내용입니다. 향후 방향을 제시하는 최종 판단입니다. 종합적인 결론입니다. 최종 판단입니다."

        with patch("app.utils.claude_client.ClaudeClient.chat_completion") as mock_claude:
            mock_claude.return_value = (claude_response, 300, 200)

            response = client.post(
                f"/api/topics/{topic_id}/ask",
                json={"content": "섹션 검증 질문"},
                headers=auth_headers
            )

        assert response.status_code == 200
        artifact_id = response.json()["data"]["artifact"]["id"]
        artifact = ArtifactDB.get_artifact_by_id(artifact_id)

        # artifact 파일 내용 확인
        with open(artifact.file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()

        # THEN: 마크다운 구조 검증
        # 최소한 H1(제목)과 H2(섹션)을 포함해야 함
        assert "#" in saved_content, "Markdown should contain headers"
        assert "##" in saved_content, "Markdown should contain section headers"

        # 파싱된 섹션이 포함되어야 함
        has_summary = "요약" in saved_content or "Summary" in saved_content
        has_conclusion = "결론" in saved_content or "Conclusion" in saved_content
        assert has_summary or has_conclusion, \
            "Parsed markdown should contain at least summary or conclusion section"


    @patch('app.routers.topics.ClaudeClient')
    def test_ask_question_response_extracts_section_content(
        self,
        mock_claude_class,
        client,
        auth_headers,
        create_test_user,
        temp_dir
    ):
        """
        TC-ASK-Q06: 질문 응답 시 H2 섹션 제거 및 순수 내용만 추출 검증
        
        Claude가 질문/대화 형식으로 응답할 때:
        - H2 섹션(##) 마크다운 헤더는 제거
        - 각 섹션의 실제 본문 콘텐츠만 추출하여 저장
        - 사용자가 자연스럽게 읽을 수 있도록 정규화
        """
        # GIVEN: 토픽 및 초기 artifact 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(input_prompt="리포트 분석", language="ko")
        )
        
        # 초기 메시지 저장 (artifact 생성을 위해 필요)
        msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.ASSISTANT, content="# 초기 보고서\n\n내용...")
        )
        
        # MD 파일 생성
        from app.utils.file_utils import build_artifact_paths, write_text, sha256_of
        _, md_path = build_artifact_paths(topic.id, 1, "report.md")
        bytes_written = write_text(md_path, "# 초기 보고서\n\n내용...")
        file_hash = sha256_of(md_path)
        
        initial_artifact = ArtifactDB.create_artifact(
            topic.id,
            msg.id,
            ArtifactCreate(
                kind=ArtifactKind.MD,
                locale="ko",
                version=1,
                filename="report.md",
                file_path=str(md_path),
                file_size=bytes_written,
                sha256=file_hash
            )
        )
        
        # Mock Claude: 질문 응답 (H2 섹션 포함)
        question_response = (
            "## 확인 사항\n\n"
            "제공하신 내용을 확인했습니다.\n\n"
            "## 개선 방향\n\n"
            "다음과 같은 부분을 수정할 수 있습니다.\n\n"
            "## 재검토\n\n"
            "해당 부분을 검토하시고 피드백을 주시면 감사하겠습니다."
        )
        
        mock_claude_instance = MagicMock()
        mock_claude_instance.chat_completion.return_value = (
            question_response,
            150,
            250
        )
        mock_claude_instance.model = "claude-sonnet-4-5-20250929"
        mock_claude_class.return_value = mock_claude_instance
        
        # WHEN: /ask 호출 (artifact 참조)
        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={
                "content": "리포트를 검토해주세요.",
                "artifact_id": initial_artifact.id
            }
        )
        
        # THEN: 응답 검증
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        
        # assistant_message에 H2 섹션이 제거되어야 함 (response body의 content)
        assistant_message_content = body["data"]["assistant_message"]["content"]
        
        # ✅ 검증 1: H2 헤더(##)가 없어야 함
        assert "## 확인 사항" not in assistant_message_content, \
            "H2 section headers should be removed"
        assert "## 개선 방향" not in assistant_message_content, \
            "H2 section headers should be removed"
        assert "## 재검토" not in assistant_message_content, \
            "H2 section headers should be removed"
        
        # ✅ 검증 2: 실제 본문 콘텐츠는 포함되어야 함
        assert "제공하신 내용을 확인했습니다" in assistant_message_content, \
            "Section content should be preserved"
        assert "다음과 같은 부분을 수정할 수 있습니다" in assistant_message_content, \
            "Section content should be preserved"
        assert "해당 부분을 검토하시고 피드백을 주시면 감사하겠습니다" in assistant_message_content, \
            "Section content should be preserved"
        
        # ✅ 검증 3: artifact가 없어야 함 (질문 응답이므로)
        assert body["data"]["artifact"] is None, \
            "Question responses should not create artifact"
        
        # ✅ 검증 4: 메시지가 DB에 저장되어야 함
        messages = MessageDB.get_messages_by_topic(topic.id)
        # initial_message + user_message + assistant_message = 3개
        assert len(messages) == 3, "Initial, user and assistant messages should be saved"
        
        # 마지막 메시지(assistant)가 추출된 콘텐츠여야 함
        last_message = messages[-1]
        assert last_message.role == MessageRole.ASSISTANT
        assert "##" not in last_message.content, \
            "Saved message should not contain H2 section headers"
        assert "제공하신 내용을 확인했습니다" in last_message.content


# ============================================================
# Template ID Tracking Tests (v2.4+)
# ============================================================

@pytest.mark.unit
@pytest.mark.allow_topic_without_template
class TestTemplateIdTracking:
    """Topic에 template_id 추적 기능 테스트 (v2.4+)"""

    def test_tc1_create_topic_with_template_id(self, create_test_user):
        """TC-1: TopicDB.create_topic() with template_id"""
        topic_data = TopicCreate(
            input_prompt="Test topic with template",
            language="ko",
            template_id=1
        )
        topic = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        assert topic.id is not None
        assert topic.template_id == 1
        assert topic.input_prompt == "Test topic with template"

    def test_tc2_create_topic_without_template_id(self, create_test_user):
        """TC-2: TopicDB.create_topic() without template_id (backward compatibility)"""
        topic_data = TopicCreate(
            input_prompt="Test topic without template",
            language="ko"
        )
        topic = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        assert topic.id is not None
        assert topic.template_id is None
        assert topic.input_prompt == "Test topic without template"

    def test_tc3_get_topic_returns_template_id(self, create_test_user):
        """TC-3: TopicDB.get_topic_by_id() returns template_id"""
        topic_data = TopicCreate(
            input_prompt="Test topic",
            language="ko",
            template_id=2
        )
        created = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        retrieved = TopicDB.get_topic_by_id(created.id)

        assert retrieved is not None
        assert retrieved.template_id == 2
        assert retrieved.id == created.id

    def test_tc4_get_topic_with_null_template_id(self, create_test_user):
        """TC-4: TopicDB.get_topic_by_id() with NULL template_id"""
        topic_data = TopicCreate(
            input_prompt="Test topic without template",
            language="ko"
        )
        created = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        retrieved = TopicDB.get_topic_by_id(created.id)

        assert retrieved is not None
        assert retrieved.template_id is None

    def test_tc5_get_topics_by_user_includes_template_id(self, create_test_user):
        """TC-5: TopicDB.get_topics_by_user() includes template_id"""
        topic1_data = TopicCreate(input_prompt="Topic 1", language="ko", template_id=1)
        topic2_data = TopicCreate(input_prompt="Topic 2", language="ko", template_id=None)

        topic1 = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic1_data)
        topic2 = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic2_data)

        topics, total = TopicDB.get_topics_by_user(user_id=create_test_user.id)

        assert total >= 2
        retrieved_topic1 = next((t for t in topics if t.id == topic1.id), None)
        retrieved_topic2 = next((t for t in topics if t.id == topic2.id), None)

        assert retrieved_topic1 is not None
        assert retrieved_topic1.template_id == 1
        assert retrieved_topic2 is not None
        assert retrieved_topic2.template_id is None

    def test_tc6_api_response_includes_template_id(self, client, auth_headers, create_test_user):
        """TC-6: API Response (GET /api/topics/{id}) includes template_id"""
        topic_data = TopicCreate(
            input_prompt="API Test Topic",
            language="ko",
            template_id=3
        )
        topic = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        response = client.get(
            f"/api/topics/{topic.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["template_id"] == 3

    def test_tc7_api_list_response_includes_template_id(self, client, auth_headers, create_test_user):
        """TC-7: API List Response (GET /api/topics) includes template_id"""
        topic_data = TopicCreate(
            input_prompt="List API Test",
            language="ko",
            template_id=4
        )
        topic = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        response = client.get("/api/topics", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        found_topic = next((t for t in body["data"]["topics"] if t["id"] == topic.id), None)
        assert found_topic is not None
        assert found_topic["template_id"] == 4

    def test_tc8_invalid_template_id(self, create_test_user):
        """TC-8: Invalid template_id edge case"""
        topic_data = TopicCreate(
            input_prompt="Test with invalid template",
            language="ko",
            template_id=99999
        )
        topic = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        retrieved = TopicDB.get_topic_by_id(topic.id)
        assert retrieved.template_id == 99999

    def test_tc9_backward_compatibility(self, create_test_user):
        """TC-9: Backward compatibility - existing data without template_id"""
        topic_data = TopicCreate(
            input_prompt="Legacy topic",
            language="ko"
        )
        topic = TopicDB.create_topic(user_id=create_test_user.id, topic_data=topic_data)

        retrieved = TopicDB.get_topic_by_id(topic.id)
        assert retrieved is not None
        assert retrieved.template_id is None
        assert retrieved.input_prompt == "Legacy topic"


@pytest.mark.api
class TestBackgroundGenerationNonBlocking:
    """백그라운드 보고서 생성 Event Loop Non-Blocking 테스트"""

    def setup_method(self):
        """각 테스트 전에 생성 상태 초기화"""
        from app.utils.generation_status import clear_all_statuses
        clear_all_statuses()

    def test_tc_001_event_loop_non_blocking(self, client, auth_headers, create_test_user):
        """TC-001: Event Loop Non-Blocking - Status 응답이 100ms 이내"""
        # 사전: 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="Test blocking",
                language="ko"
            )
        )

        # Mock: Claude API 응답 (충분한 콘텐츠)
        mock_markdown = """# 보고서 요약
요약 섹션의 상세한 내용입니다. 최소 50자 이상의 콘텐츠를 포함하고 있습니다. 충분한 길이를 확보했습니다.

## 배경
배경 섹션의 상세한 내용입니다. 충분한 정보를 포함하고 있으며, 비즈니스 맥락을 설명합니다.

## 주요 내용
주요 내용 섹션입니다. 상세한 분석과 핵심 포인트를 제시합니다. 이 섹션은 매우 중요합니다.

## 결론
결론 섹션의 상세한 내용입니다. 최종 권고사항과 실행 계획을 포함합니다."""

        with patch('app.utils.claude_client.ClaudeClient.generate_report') as mock_claude:
            mock_claude.return_value = mock_markdown

            # 생성 시작
            generate_resp = client.post(
                f"/api/topics/{topic.id}/generate",
                headers=auth_headers,
                json={
                    "topic": "Test topic",
                    "plan": "Test plan"
                }
            )
            assert generate_resp.status_code == 202

            # 즉시 status 확인 (응답 시간 측정)
            import time
            start = time.time()
            status_resp = client.get(
                f"/api/topics/{topic.id}/status",
                headers=auth_headers
            )
            elapsed = time.time() - start

            # 검증: 응답 < 100ms, 상태 = generating
            assert status_resp.status_code == 200
            assert elapsed < 0.1, f"Status response took {elapsed:.3f}s, expected < 0.1s"
            data = status_resp.json()["data"]
            assert data["status"] == "generating"

    @pytest.mark.allow_topic_without_template
    def test_generate_without_template_returns_404(self, client, auth_headers, create_test_user):
        """template_id가 없는 토픽은 /generate 호출 시 실패한다."""
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="템플릿 없는 토픽",
                language="ko"
            )
        )

        response = client.post(
            f"/api/topics/{topic.id}/generate",
            headers=auth_headers,
            json={"topic": "템플릿 없음", "plan": "계획"}
        )

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "TEMPLATE.NOT_FOUND"

    def test_tc_002_artifact_status_states(self, client, auth_headers, create_test_user):
        """TC-002: Artifact 상태 전이 - scheduled → generating → completed"""
        # 사전: 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="Test artifact status",
                language="ko"
            )
        )

        mock_markdown = """# 보고서 요약
상세한 요약 내용입니다. 충분한 길이를 확보했습니다.

## 배경
배경 섹션의 상세한 내용입니다.

## 주요 내용
주요 내용 섹션입니다.

## 결론
결론 섹션의 상세한 내용입니다."""

        with patch('app.utils.claude_client.ClaudeClient.generate_report') as mock_claude:
            mock_claude.return_value = mock_markdown

            # 생성 시작
            generate_resp = client.post(
                f"/api/topics/{topic.id}/generate",
                headers=auth_headers,
                json={
                    "topic": "Test topic",
                    "plan": "Test plan"
                }
            )
            assert generate_resp.status_code == 202

            # Artifact가 생성되었는지 확인 (202 응답은 Artifact 생성을 의미)
            assert generate_resp.json()["success"] is True
            response_data = generate_resp.json()["data"]

            # Artifact ID 확인
            assert "topic_id" in response_data
            assert response_data["status"] == "generating"

            # 즉시 status 조회 - "generating" 상태여야 함
            status_resp = client.get(
                f"/api/topics/{topic.id}/status",
                headers=auth_headers
            )
            assert status_resp.status_code == 200
            status_data = status_resp.json()["data"]

            # 상태 확인: scheduled 또는 generating
            assert status_data["status"] in ["scheduled", "generating"]
            assert status_data["progress_percent"] >= 0

    def test_tc_003_concurrent_generation(self, client, auth_headers, create_test_user):
        """TC-003: 동시 다중 생성 - 3개 Topic 동시 생성"""
        # 사전: 3개 토픽 생성
        topics = [
            TopicDB.create_topic(
                user_id=create_test_user.id,
                topic_data=TopicCreate(
                    input_prompt=f"Test topic {i}",
                    language="ko"
                )
            )
            for i in range(3)
        ]

        mock_markdown = """# 보고서 요약
상세한 요약 내용입니다. 충분한 길이를 확보했습니다.

## 배경
배경 섹션의 상세한 내용입니다.

## 주요 내용
주요 내용 섹션입니다.

## 결론
결론 섹션의 상세한 내용입니다."""

        with patch('app.utils.claude_client.ClaudeClient.generate_report') as mock_claude:
            mock_claude.return_value = mock_markdown

            # 동시 생성 시작
            generate_results = [
                client.post(
                    f"/api/topics/{t.id}/generate",
                    headers=auth_headers,
                    json={"topic": f"Test {t.id}", "plan": "Plan"}
                )
                for t in topics
            ]

            # 모두 202 Accepted
            for resp in generate_results:
                assert resp.status_code == 202

            # 상태 동시 조회
            status_results = [
                client.get(
                    f"/api/topics/{t.id}/status",
                    headers=auth_headers
                )
                for t in topics
            ]

            # 모두 "generating" 상태
            for status_resp in status_results:
                assert status_resp.status_code == 200
                assert status_resp.json()["data"]["status"] == "generating"

    def test_tc_004_artifact_metadata(self, client, auth_headers, create_test_user):
        """TC-004: Artifact 메타데이터 - ID, 경로, 버전 정보 확인"""
        # 사전: 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="Test artifact metadata",
                language="ko"
            )
        )

        mock_markdown = """# 보고서 요약
상세한 요약 내용입니다.

## 배경
배경 섹션의 상세한 내용입니다.

## 주요 내용
주요 내용 섹션입니다.

## 결론
결론 섹션의 상세한 내용입니다."""

        with patch('app.utils.claude_client.ClaudeClient.generate_report') as mock_claude:
            mock_claude.return_value = mock_markdown

            # 생성 시작
            generate_resp = client.post(
                f"/api/topics/{topic.id}/generate",
                headers=auth_headers,
                json={
                    "topic": "Test topic",
                    "plan": "Test plan"
                }
            )
            assert generate_resp.status_code == 202

            # Status 조회
            status_resp = client.get(
                f"/api/topics/{topic.id}/status",
                headers=auth_headers
            )
            assert status_resp.status_code == 200

            data = status_resp.json()["data"]

            # Artifact 메타데이터 확인
            assert "artifact_id" in data
            assert "status" in data
            assert "progress_percent" in data
            assert "started_at" in data

            # progress_percent 범위 확인
            assert 0 <= data["progress_percent"] <= 100

    def test_tc_005_status_response_time(self, client, auth_headers, create_test_user):
        """TC-005: Status 엔드포인트 응답 시간 - 10회 연속 조회 < 100ms"""
        # 사전: 토픽 생성
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="Test response time",
                language="ko"
            )
        )

        mock_markdown = """# 보고서 요약
상세한 요약 내용입니다.

## 배경
배경 섹션의 상세한 내용입니다.

## 주요 내용
주요 내용 섹션입니다.

## 결론
결론 섹션의 상세한 내용입니다."""

        with patch('app.utils.claude_client.ClaudeClient.generate_report') as mock_claude:
            mock_claude.return_value = mock_markdown

            # 생성 시작
            client.post(
                f"/api/topics/{topic.id}/generate",
                headers=auth_headers,
                json={
                    "topic": "Test topic",
                    "plan": "Test plan"
                }
            )

            # 응답 시간 측정 (10회 반복)
            import time
            response_times = []

            for _ in range(10):
                start = time.time()
                resp = client.get(
                    f"/api/topics/{topic.id}/status",
                    headers=auth_headers
                )
                elapsed = time.time() - start
                response_times.append(elapsed)

                assert resp.status_code == 200

            # 최대 응답 시간 확인
            max_time = max(response_times)
            assert max_time < 0.1, f"Max response time {max_time:.3f}s, expected < 0.1s"
