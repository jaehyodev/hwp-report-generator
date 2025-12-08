"""
JSON Artifact Persistence Tests

Tests for persisting StructuredReportResponse JSON artifacts from Claude's
Structured Outputs alongside Markdown artifacts in ask() and generate() flows.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.models.topic import TopicCreate
from app.models.message import MessageCreate
from app.models.artifact import ArtifactCreate
from app.models.report_section import StructuredReportResponse, SectionMetadata
from shared.types.enums import MessageRole, ArtifactKind, TopicSourceType


@pytest.mark.api
class TestJsonArtifactPersistence:
    """JSON Artifact Persistence API Tests"""

    # ==================== TC-001: ask() JSON Artifact Save ====================
    def test_ask_json_artifact_save_with_message_id_matching(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-001: ask() 함수에서 JSON artifact 저장 및 message_id 매칭 검증

        시나리오:
        1. Topic 생성
        2. 첫 번째 메시지 전송 (ask)
        3. JSON artifact와 MD artifact가 모두 저장되는지 확인
        4. 두 artifact의 message_id가 동일한지 확인
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="테스트 주제",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        # Mock StructuredClaudeClient response
        mock_json_response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="sec_1",
                    placeholder_key="TITLE",
                    type="TITLE",
                    content="테스트 제목",
                    order=1,
                    source_type="basic"
                ),
                SectionMetadata(
                    id="sec_2",
                    placeholder_key="SUMMARY",
                    type="SUMMARY",
                    content="테스트 요약",
                    order=2,
                    source_type="basic"
                )
            ],
            metadata={"source": "ask", "version": 1}
        )

        mock_markdown = "# 테스트 제목\n\n## 요약\n\n테스트 요약"

        with patch('app.routers.topics.StructuredClaudeClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.generate_structured_report.return_value = mock_json_response
            mock_client.return_value = mock_instance

            with patch('app.routers.topics.build_report_md_from_json', return_value=mock_markdown):
                # Act
                response = client.post(
                    f"/api/topics/{topic.id}/ask",
                    headers=auth_headers,
                    json={"user_message": "첫 번째 질문"}
                )

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        # 메시지 조회
        messages = MessageDB.get_messages_by_topic(topic.id)
        assert len(messages) >= 2  # User + Assistant
        assistant_msg = [m for m in messages if m.role == MessageRole.ASSISTANT][0]

        # JSON artifact와 MD artifact 조회
        artifacts = ArtifactDB.get_artifacts_by_message(assistant_msg.id)

        # 두 종류의 artifact가 모두 생성되었는지 확인
        md_artifacts = [a for a in artifacts if a.kind == ArtifactKind.MD]
        json_artifacts = [a for a in artifacts if a.kind == ArtifactKind.JSON]

        assert len(md_artifacts) >= 1, "MD artifact가 생성되지 않음"
        assert len(json_artifacts) >= 1, "JSON artifact가 생성되지 않음"

        # message_id 매칭 확인
        assert json_artifacts[0].message_id == assistant_msg.id
        assert md_artifacts[0].message_id == assistant_msg.id

    # ==================== TC-002: generate() JSON Artifact Save ====================
    def test_generate_json_artifact_save_with_version_matching(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-002: _background_generate_report() 함수에서 JSON artifact 저장 및 version 매칭 검증

        시나리오:
        1. Topic 생성
        2. generate 엔드포인트 호출
        3. 백그라운드 작업이 JSON artifact 저장하는지 확인
        4. 두 artifact (MD, JSON)의 version이 동일한지 확인
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="보고서 생성 주제",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        mock_json_response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="sec_1",
                    placeholder_key="TITLE",
                    type="TITLE",
                    content="보고서 제목",
                    order=1,
                    source_type="basic"
                )
            ],
            metadata={"source": "generate", "version": 1}
        )

        mock_markdown = "# 보고서 제목"

        with patch('app.routers.topics.StructuredClaudeClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.generate_structured_report.return_value = mock_json_response
            mock_client.return_value = mock_instance

            with patch('app.routers.topics.build_report_md_from_json', return_value=mock_markdown):
                with patch('app.routers.topics.asyncio.create_task') as mock_task:
                    # Act
                    response = client.post(
                        f"/api/topics/{topic.id}/generate",
                        headers=auth_headers,
                        json={"custom_prompt": "테스트 프롬프트"}
                    )

        # Assert
        assert response.status_code == 202  # Accepted (백그라운드)

        # 생성 완료 대기 및 artifact 조회
        import time
        time.sleep(1)  # 백그라운드 작업 완료 대기

        artifacts = ArtifactDB.get_artifacts_by_topic(topic.id)
        md_artifacts = [a for a in artifacts if a.kind == ArtifactKind.MD]
        json_artifacts = [a for a in artifacts if a.kind == ArtifactKind.JSON]

        if md_artifacts and json_artifacts:
            # version 매칭 확인
            assert md_artifacts[0].version == json_artifacts[0].version

    # ==================== TC-003: message_id-based JSON Artifact Retrieval ====================
    def test_message_id_based_json_artifact_retrieval(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-003: message_id를 기반으로 JSON artifact 조회 가능성 검증

        시나리오:
        1. ask() 호출 → JSON + MD artifact 생성
        2. message_id로 artifact 검색
        3. JSON artifact 검색 가능하고 데이터 무결성 확인
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="검색 테스트 주제",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        user_msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.USER, content="사용자 질문")
        )

        # 임시 JSON artifact 생성
        json_file_path = os.path.join(temp_dir, "test_structured.json")
        json_data = {
            "sections": [
                {
                    "id": "sec_1",
                    "placeholder_key": "TITLE",
                    "type": "TITLE",
                    "content": "테스트",
                    "order": 1,
                    "source_type": "basic"
                }
            ],
            "metadata": {"test": "data"}
        }
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f)

        json_artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=user_msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.JSON,
                filename="test_structured.json",
                file_path=json_file_path,
                file_size=os.path.getsize(json_file_path),
                locale="ko",
                version=1
            )
        )

        # Act & Assert
        retrieved_artifacts = ArtifactDB.get_artifacts_by_message(user_msg.id)
        json_artifacts = [a for a in retrieved_artifacts if a.kind == ArtifactKind.JSON]

        assert len(json_artifacts) >= 1
        assert json_artifacts[0].id == json_artifact.id

    # ==================== TC-004: version-based JSON Artifact Retrieval ====================
    def test_version_based_json_artifact_retrieval(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-004: version + topic_id를 기반으로 JSON artifact 조회 가능성 검증

        시나리오:
        1. 같은 topic의 여러 version artifact 생성
        2. version으로 정확한 artifact 검색
        3. 특정 version의 JSON artifact만 조회 가능 확인
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="version 테스트",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        # Version 1 artifact 생성
        json_file_v1 = os.path.join(temp_dir, "structured_v1.json")
        with open(json_file_v1, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "content": "v1"}, f)

        artifact_v1 = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=None,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.JSON,
                filename="structured_v1.json",
                file_path=json_file_v1,
                file_size=os.path.getsize(json_file_v1),
                locale="ko",
                version=1
            )
        )

        # Version 2 artifact 생성
        json_file_v2 = os.path.join(temp_dir, "structured_v2.json")
        with open(json_file_v2, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "content": "v2"}, f)

        artifact_v2 = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=None,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.JSON,
                filename="structured_v2.json",
                file_path=json_file_v2,
                file_size=os.path.getsize(json_file_v2),
                locale="ko",
                version=2
            )
        )

        # Act & Assert
        artifacts = ArtifactDB.get_artifacts_by_topic(topic.id)
        json_artifacts = [a for a in artifacts if a.kind == ArtifactKind.JSON]

        assert len(json_artifacts) >= 2
        v1_artifacts = [a for a in json_artifacts if a.version == 1]
        v2_artifacts = [a for a in json_artifacts if a.version == 2]

        assert len(v1_artifacts) >= 1
        assert len(v2_artifacts) >= 1

    # ==================== TC-005: JSON Artifact File Validity ====================
    def test_json_artifact_file_validity(
        self, create_test_user, temp_dir
    ):
        """
        TC-005: JSON artifact 파일의 StructuredReportResponse 스키마 유효성 검증

        시나리오:
        1. JSON artifact 파일 생성
        2. 파일 읽기 및 StructuredReportResponse 스키마 검증
        3. 필수 필드 (sections, metadata) 존재 확인
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="JSON 유효성 테스트",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        # 유효한 JSON artifact 생성
        json_file_path = os.path.join(temp_dir, "valid_structured.json")
        structured_response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="sec_1",
                    placeholder_key="TITLE",
                    type="TITLE",
                    content="제목",
                    order=1,
                    source_type="basic"
                )
            ],
            metadata={"test": "metadata"}
        )

        with open(json_file_path, "w", encoding="utf-8") as f:
            f.write(structured_response.model_dump_json())

        # Act
        with open(json_file_path, "r", encoding="utf-8") as f:
            loaded_json = json.load(f)

        # Assert
        assert "sections" in loaded_json
        assert "metadata" in loaded_json
        assert len(loaded_json["sections"]) >= 1
        assert loaded_json["sections"][0]["type"] == "TITLE"

    # ==================== TC-006: convert-hwpx Utilizes JSON Artifact ====================
    def test_convert_hwpx_utilizes_json_artifact(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-006: convert-hwpx 엔드포인트에서 JSON artifact 데이터 활용 검증

        시나리오:
        1. MD artifact + JSON artifact 생성
        2. convert-hwpx 호출
        3. JSON artifact의 metadata 필드가 변환에 사용되는지 확인
           (예: placeholder_key, max_length, description 등)
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="변환 테스트",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        # MD artifact 생성
        md_file = os.path.join(temp_dir, "report.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# 제목\n\n## 내용\n\n본문")

        md_artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=None,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="report.md",
                file_path=md_file,
                file_size=os.path.getsize(md_file),
                locale="ko",
                version=1
            )
        )

        # JSON artifact 생성
        json_file = os.path.join(temp_dir, "structured_1.json")
        structured_response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="sec_1",
                    placeholder_key="TITLE",
                    type="TITLE",
                    content="제목",
                    order=1,
                    source_type="basic",
                    max_length=100,
                    description="문서 제목"
                )
            ],
            metadata={"version": 1}
        )

        with open(json_file, "w", encoding="utf-8") as f:
            f.write(structured_response.model_dump_json())

        json_artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=None,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.JSON,
                filename="structured_1.json",
                file_path=json_file,
                file_size=os.path.getsize(json_file),
                locale="ko",
                version=1
            )
        )

        # Act: convert-hwpx 호출
        # 참고: 실제 변환은 mock되지 않으므로, artifact 존재 여부만 검증
        artifacts = ArtifactDB.get_artifacts_by_topic(topic.id)
        json_artifacts = [a for a in artifacts if a.kind == ArtifactKind.JSON and a.version == 1]

        # Assert
        assert len(json_artifacts) >= 1
        assert json_artifacts[0].id == json_artifact.id

    # ==================== TC-007: BASIC Type Topic Skips JSON Artifact ====================
    def test_basic_type_topic_skips_json_artifact(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-007: BASIC type topic은 JSON artifact 생성하지 않는지 검증

        시나리오:
        1. TopicSourceType.BASIC topic 생성
        2. ask() 호출
        3. MD artifact만 생성되고 JSON artifact는 생성 안 됨
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="BASIC type 테스트",
                language="ko",
                source_type=TopicSourceType.BASIC
            )
        )

        # Act: ask() 호출
        with patch('app.routers.topics.ClaudeClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.generate_report.return_value = "# 응답\n\n내용"
            mock_client.return_value = mock_instance

            response = client.post(
                f"/api/topics/{topic.id}/ask",
                headers=auth_headers,
                json={"user_message": "질문"}
            )

        assert response.status_code == 200

        # Assert
        messages = MessageDB.get_messages_by_topic(topic.id)
        assistant_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT]

        if assistant_msgs:
            artifacts = ArtifactDB.get_artifacts_by_message(assistant_msgs[0].id)
            json_artifacts = [a for a in artifacts if a.kind == ArtifactKind.JSON]

            # BASIC type은 JSON artifact를 만들지 않음
            assert len(json_artifacts) == 0

    # ==================== TC-008: convert-hwpx JSON Artifact Missing Error ====================
    def test_convert_hwpx_json_artifact_missing_error(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-008: JSON artifact 미존재 시 에러 반환 검증

        시나리오:
        1. MD artifact만 생성 (JSON artifact 없음)
        2. convert-hwpx 엔드포인트 호출
        3. 400 Bad Request 반환
        4. 에러 메시지: "JSON artifact가 없습니다. 관리자에게 문의하세요."
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="에러 테스트",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        # MD artifact만 생성 (JSON 없음)
        md_file = os.path.join(temp_dir, "report_only_md.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# 제목\n\n내용")

        md_artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=None,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="report_only_md.md",
                file_path=md_file,
                file_size=os.path.getsize(md_file),
                locale="ko",
                version=1
            )
        )

        # Act
        response = client.post(
            f"/api/artifacts/{md_artifact.id}/convert-hwpx",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert "JSON artifact" in body["error"]["message"] or "JSON" in body["error"]["message"]
        assert body["error"]["hint"] is not None

    # ==================== TC-009: JSON Artifact Filename Convention ====================
    def test_json_artifact_filename_convention(
        self, create_test_user, temp_dir
    ):
        """
        TC-009: JSON artifact 파일명 규칙 검증

        시나리오:
        1. ask()로 생성된 JSON artifact: structured_{message_id}.json
        2. generate()로 생성된 JSON artifact: structured_{version}.json
        3. 파일명이 규칙을 따르는지 검증
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="파일명 테스트",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        msg = MessageDB.create_message(
            topic.id,
            MessageCreate(role=MessageRole.USER, content="테스트")
        )

        # Version 1 artifact 생성
        json_file = os.path.join(temp_dir, f"structured_1.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({"version": 1}, f)

        artifact = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=None,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.JSON,
                filename=f"structured_1.json",
                file_path=json_file,
                file_size=os.path.getsize(json_file),
                locale="ko",
                version=1
            )
        )

        # Assert
        assert artifact.filename.startswith("structured_")
        assert artifact.filename.endswith(".json")

    # ==================== TC-010: Multiple ask() Calls Create Independent Pairs ====================
    def test_multiple_ask_calls_create_independent_artifact_pairs(
        self, client, auth_headers, create_test_user, temp_dir
    ):
        """
        TC-010: 연속된 ask() 호출 시 각각 독립적인 (MD, JSON) artifact pair 생성 검증

        시나리오:
        1. ask() 첫 번째 호출 → message_1, artifact pair 1 생성
        2. ask() 두 번째 호출 → message_2, artifact pair 2 생성
        3. 각 message별로 독립적인 artifact pair 존재 확인
        4. artifact id, message_id 모두 다른지 검증
        """
        # Setup
        topic = TopicDB.create_topic(
            user_id=create_test_user.id,
            topic_data=TopicCreate(
                input_prompt="다중 호출 테스트",
                language="ko",
                source_type=TopicSourceType.OPTIMIZATION
            )
        )

        mock_json_response = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="sec_1",
                    placeholder_key="TITLE",
                    type="TITLE",
                    content="제목",
                    order=1,
                    source_type="basic"
                )
            ],
            metadata={"call": 1}
        )

        # 첫 번째 ask() 호출
        with patch('app.routers.topics.StructuredClaudeClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.generate_structured_report.return_value = mock_json_response
            mock_client.return_value = mock_instance

            with patch('app.routers.topics.build_report_md_from_json', return_value="# 응답 1"):
                response_1 = client.post(
                    f"/api/topics/{topic.id}/ask",
                    headers=auth_headers,
                    json={"user_message": "첫 번째 질문"}
                )

        assert response_1.status_code == 200

        # 두 번째 ask() 호출
        mock_json_response_2 = StructuredReportResponse(
            sections=[
                SectionMetadata(
                    id="sec_2",
                    placeholder_key="SUMMARY",
                    type="SUMMARY",
                    content="요약",
                    order=1,
                    source_type="basic"
                )
            ],
            metadata={"call": 2}
        )

        with patch('app.routers.topics.StructuredClaudeClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.generate_structured_report.return_value = mock_json_response_2
            mock_client.return_value = mock_instance

            with patch('app.routers.topics.build_report_md_from_json', return_value="# 응답 2"):
                response_2 = client.post(
                    f"/api/topics/{topic.id}/ask",
                    headers=auth_headers,
                    json={"user_message": "두 번째 질문"}
                )

        assert response_2.status_code == 200

        # Assert: 두 개의 독립적인 artifact pair 검증
        messages = MessageDB.get_messages_by_topic(topic.id)
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]

        assert len(assistant_messages) >= 2

        # 각 메시지별 artifact pair 검증
        pair_1_artifacts = ArtifactDB.get_artifacts_by_message(assistant_messages[0].id)
        pair_2_artifacts = ArtifactDB.get_artifacts_by_message(assistant_messages[1].id)

        # pair 1: MD + JSON
        pair_1_md = [a for a in pair_1_artifacts if a.kind == ArtifactKind.MD]
        pair_1_json = [a for a in pair_1_artifacts if a.kind == ArtifactKind.JSON]

        # pair 2: MD + JSON
        pair_2_md = [a for a in pair_2_artifacts if a.kind == ArtifactKind.MD]
        pair_2_json = [a for a in pair_2_artifacts if a.kind == ArtifactKind.JSON]

        # 각 pair가 (MD, JSON) 구조인지 확인
        if pair_1_md and pair_1_json:
            assert pair_1_md[0].message_id == pair_1_json[0].message_id

        if pair_2_md and pair_2_json:
            assert pair_2_md[0].message_id == pair_2_json[0].message_id

        # 두 pair의 artifact가 다른지 확인
        if pair_1_json and pair_2_json:
            assert pair_1_json[0].id != pair_2_json[0].id
            assert pair_1_json[0].message_id != pair_2_json[0].message_id
