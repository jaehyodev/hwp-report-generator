"""
아티팩트 API 라우터 테스트
"""
import os
import pytest

from app.database.topic_db import TopicDB
from app.database.message_db import MessageDB
from app.database.artifact_db import ArtifactDB
from app.models.topic import TopicCreate
from app.models.message import MessageCreate
from app.models.artifact import ArtifactCreate
from shared.types.enums import MessageRole, ArtifactKind, TopicSourceType


def _create_topic_message(user_id):
    topic = TopicDB.create_topic(user_id=user_id, topic_data=TopicCreate(input_prompt="Artifact Topic", language="ko", source_type=TopicSourceType.BASIC))
    msg = MessageDB.create_message(topic.id, MessageCreate(role=MessageRole.USER, content="생성 메시지"))
    return topic, msg


@pytest.mark.api
class TestArtifactsRouter:
    """Artifacts API 테스트"""

    def test_get_artifact_success(self, client, auth_headers, create_test_user, temp_dir):
        topic, msg = _create_topic_message(create_test_user.id)
        file_path = os.path.join(temp_dir, "report_v1.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# 테스트 리포트\n내용")

        art = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="report_v1.md",
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(f"/api/artifacts/{art.id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == art.id

    def test_get_artifact_unauthorized(self, client, auth_headers, create_test_admin, temp_dir):
        topic, msg = _create_topic_message(create_test_admin.id)
        file_path = os.path.join(temp_dir, "admin_art.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("admin")

        art = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="admin_art.md",
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(f"/api/artifacts/{art.id}", headers=auth_headers)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "TOPIC.UNAUTHORIZED"

    def test_get_artifact_not_found(self, client, auth_headers):
        resp = client.get("/api/artifacts/999999", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ARTIFACT.NOT_FOUND"

    def test_get_artifact_content_success_md(self, client, auth_headers, create_test_user, temp_dir):
        topic, msg = _create_topic_message(create_test_user.id)
        file_path = os.path.join(temp_dir, "content.md")
        content = "# 헤더\n본문"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        art = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="content.md",
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(f"/api/artifacts/{art.id}/content", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["content"] == content

    def test_get_artifact_content_wrong_kind(self, client, auth_headers, create_test_user, temp_dir):
        topic, msg = _create_topic_message(create_test_user.id)
        file_path = os.path.join(temp_dir, "file.hwpx")
        with open(file_path, "wb") as f:
            f.write(b"dummy")

        art = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.HWPX,
                filename="file.hwpx",
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(f"/api/artifacts/{art.id}/content", headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "ARTIFACT.INVALID_KIND"

    def test_download_artifact_success(self, client, auth_headers, create_test_user, temp_dir):
        topic, msg = _create_topic_message(create_test_user.id)
        file_path = os.path.join(temp_dir, "dl.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("download")

        art = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="dl.md",
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(f"/api/artifacts/{art.id}/download", headers=auth_headers)
        assert resp.status_code == 200

    def test_download_artifact_missing_file(self, client, auth_headers, create_test_user, temp_dir):
        topic, msg = _create_topic_message(create_test_user.id)
        file_path = os.path.join(temp_dir, "missing.md")
        # intentionally do not create file

        art = ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="missing.md",
                file_path=file_path,
                file_size=0,
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(f"/api/artifacts/{art.id}/download", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ARTIFACT.NOT_FOUND"

    def test_get_artifacts_by_topic_filters(self, client, auth_headers, create_test_user, temp_dir):
        topic, msg = _create_topic_message(create_test_user.id)

        # MD ko
        md_path = os.path.join(temp_dir, "a.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("a")
        ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="a.md",
                file_path=md_path,
                file_size=os.path.getsize(md_path),
                locale="ko",
                version=1,
            ),
        )

        # HWPX ko
        hwpx_path = os.path.join(temp_dir, "b.hwpx")
        with open(hwpx_path, "wb") as f:
            f.write(b"b")
        ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.HWPX,
                filename="b.hwpx",
                file_path=hwpx_path,
                file_size=os.path.getsize(hwpx_path),
                locale="ko",
                version=1,
            ),
        )

        # MD en
        md_en_path = os.path.join(temp_dir, "c.md")
        with open(md_en_path, "w", encoding="utf-8") as f:
            f.write("c")
        ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="c.md",
                file_path=md_en_path,
                file_size=os.path.getsize(md_en_path),
                locale="en",
                version=1,
            ),
        )

        # Filter: kind=md, locale=ko
        resp = client.get(
            f"/api/artifacts/topics/{topic.id}?kind=md&locale=ko",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        arts = body["data"]["artifacts"]
        assert all(a["kind"] == ArtifactKind.MD.value for a in arts)
        assert len(arts) >= 1


    def test_get_artifact_content_not_found(self, client, auth_headers):
        """존재하지 않는 아티팩트 내용 조회"""
        resp = client.get("/api/artifacts/999999/content", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ARTIFACT.NOT_FOUND"

    def test_download_artifact_not_found(self, client, auth_headers):
        """존재하지 않는 아티팩트 다운로드"""
        resp = client.get("/api/artifacts/999999/download", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "ARTIFACT.NOT_FOUND"

    def test_get_artifacts_by_topic_not_found(self, client, auth_headers):
        """존재하지 않는 토픽의 아티팩트 조회"""
        resp = client.get("/api/artifacts/topics/999999", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "TOPIC.NOT_FOUND"

    def test_download_message_hwpx_existing(self, client, auth_headers, create_test_user, temp_dir):
        """기존 HWPX 아티팩트가 있으면 그대로 다운로드"""
        topic, msg = _create_topic_message(create_test_user.id)

        hwpx_path = os.path.join(temp_dir, "existing.hwpx")
        with open(hwpx_path, "wb") as f:
            f.write(b"existing hwpx data")

        ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.HWPX,
                filename="existing.hwpx",
                file_path=hwpx_path,
                file_size=os.path.getsize(hwpx_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(
            f"/api/artifacts/messages/{msg.id}/hwpx/download",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-hwpx"
        assert resp.content == b"existing hwpx data"

        artifacts = ArtifactDB.get_artifacts_by_message(msg.id)
        assert len(artifacts) == 1

    def test_download_message_hwpx_generates_from_md(self, client, auth_headers, create_test_user, temp_dir):
        """HWPX 없을 경우 MD에서 변환 후 다운로드"""
        topic, msg = _create_topic_message(create_test_user.id)

        md_content = """# 테스트 보고서

## 요약

요약 내용

## 배경 및 목적

배경 내용

## 주요 내용

주요 내용 상세

## 결론 및 제언

결론 내용
"""
        md_path = os.path.join(temp_dir, "report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        ArtifactDB.create_artifact(
            topic_id=topic.id,
            message_id=msg.id,
            artifact_data=ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="report.md",
                file_path=md_path,
                file_size=os.path.getsize(md_path),
                locale="ko",
                version=1,
            ),
        )

        resp = client.get(
            f"/api/artifacts/messages/{msg.id}/hwpx/download",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-hwpx"
        assert len(resp.content) > 0

        hwpx_artifact = ArtifactDB.get_latest_artifact_by_message_and_kind(
            msg.id, ArtifactKind.HWPX
        )
        assert hwpx_artifact is not None
        assert os.path.exists(hwpx_artifact.file_path)

    def test_download_message_hwpx_missing_md(self, client, auth_headers, create_test_user):
        """MD 아티팩트가 없으면 404 반환"""
        topic, msg = _create_topic_message(create_test_user.id)

        resp = client.get(
            f"/api/artifacts/messages/{msg.id}/hwpx/download",
            headers=auth_headers,
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "ARTIFACT.NOT_FOUND"

