"""
Integration tests for composed system prompt behavior in ask() and
_background_generate_report().
"""
import asyncio
import logging
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch, call

import pytest

from app.database.topic_db import TopicDB
from app.models.topic import TopicCreate
from app.models.report_section import StructuredReportResponse, SectionMetadata
from app.routers import topics as topics_module
from shared.types.enums import TopicSourceType


def _make_structured_response() -> StructuredReportResponse:
    """Return a minimal Structured Outputs response used by multiple tests."""
    return StructuredReportResponse(
        sections=[
            SectionMetadata(
                id="TITLE",
                type="TITLE",
                content="합성 보고서",
                order=1,
                source_type="basic"
            ),
            SectionMetadata(
                id="SUMMARY",
                type="SUMMARY",
                content="요약 본문",
                order=2,
                source_type="basic"
            ),
        ],
        metadata={"generated_at": "2025-01-01T10:00:00"}
    )


def _install_artifact_path_patch(monkeypatch, tmp_path):
    """Route artifact writes into the pytest tmp_path directory."""

    def _builder(topic_id: int, version: int, filename: str):
        base_dir = tmp_path / f"topic_{topic_id}" / f"v{version}"
        return base_dir, base_dir / filename

    monkeypatch.setattr("app.routers.topics.build_artifact_paths", _builder)
    return _builder


def _setup_background_env(
    monkeypatch,
    tmp_path,
    *,
    topic_id: int,
    artifact_id: int,
    prompt_user: Optional[str],
    prompt_system: Optional[str],
    template_id: Optional[int] = None,
):
    """Patch blocking dependencies so _background_generate_report() stays isolated."""
    topic_stub = SimpleNamespace(
        id=topic_id,
        source_type=TopicSourceType.BASIC,
        template_id=template_id,
        prompt_user=prompt_user,
        prompt_system=prompt_system,
        language="ko"
    )
    artifact_stub = SimpleNamespace(
        id=artifact_id,
        version=1,
        language="ko"
    )

    monkeypatch.setattr(
        topics_module.TopicDB,
        "get_topic_by_id",
        lambda _topic_id: topic_stub
    )
    monkeypatch.setattr(
        topics_module.ArtifactDB,
        "get_artifact_by_id",
        lambda _artifact_id: artifact_stub
    )

    update_mock = MagicMock()
    json_create_mock = MagicMock(
        return_value=SimpleNamespace(id=artifact_id + 1, version=artifact_stub.version)
    )
    message_mock = MagicMock(return_value=SimpleNamespace(id=artifact_id + 2, seq_no=1))
    ai_usage_mock = MagicMock()

    monkeypatch.setattr(
        topics_module.ArtifactDB,
        "update_artifact_status",
        update_mock
    )
    monkeypatch.setattr(
        topics_module.ArtifactDB,
        "create_artifact",
        json_create_mock
    )
    monkeypatch.setattr(
        topics_module.MessageDB,
        "create_message",
        message_mock
    )
    monkeypatch.setattr(
        topics_module.AiUsageDB,
        "create_ai_usage",
        ai_usage_mock
    )
    monkeypatch.setattr(
        topics_module,
        "next_artifact_version",
        lambda *args, **kwargs: artifact_stub.version
    )

    _install_artifact_path_patch(monkeypatch, tmp_path)

    return SimpleNamespace(
        topic=topic_stub,
        artifact=artifact_stub,
        update_mock=update_mock,
        json_create_mock=json_create_mock,
        message_mock=message_mock,
        ai_usage_mock=ai_usage_mock
    )


@pytest.mark.api
def test_tc_007_ask_uses_composed_prompt_for_structured_mode(
    client,
    auth_headers,
    create_test_user,
    tmp_path,
    monkeypatch
):
    """TC-007: ask() should call StructuredClaudeClient with composed prompt."""
    topic = TopicDB.create_topic(
        user_id=create_test_user.id,
        topic_data=TopicCreate(
            input_prompt="시장 리포트",
            language="ko",
            source_type=TopicSourceType.BASIC,
            prompt_user="Step 1: Planning result",
            prompt_system="Rules: Follow markdown format"
        )
    )

    structured_response = _make_structured_response()
    fake_parsed = {
        "title": "합성 보고서",
        "title_summary": "요약",
        "summary": "요약 본문",
        "title_background": "배경",
        "background": "배경 본문",
        "title_main_content": "본문",
        "main_content": "상세 본문",
        "title_conclusion": "결론",
        "conclusion": "마무리",
        "generated_at": "2025-01-01T10:00:00"
    }

    _install_artifact_path_patch(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "app.routers.topics.parse_markdown_to_content",
        lambda _: fake_parsed
    )
    monkeypatch.setattr(
        "app.routers.topics.build_report_md",
        lambda __: "# 합성 보고서"
    )
    monkeypatch.setattr(
        "app.routers.topics.AiUsageDB.create_ai_usage",
        lambda *args, **kwargs: None
    )

    with patch("app.routers.topics.StructuredClaudeClient") as mock_structured_cls, \
            patch("app.routers.topics.ClaudeClient") as mock_claude_cls:
        mock_structured = MagicMock()
        mock_structured.generate_structured_report.return_value = structured_response
        mock_structured.last_input_tokens = 120
        mock_structured.last_output_tokens = 340
        mock_structured_cls.return_value = mock_structured

        mock_claude = MagicMock()
        mock_claude.model = "claude-3-6-sonnet"
        mock_claude.last_input_tokens = 0
        mock_claude.last_output_tokens = 0
        mock_claude_cls.return_value = mock_claude

        response = client.post(
            f"/api/topics/{topic.id}/ask",
            headers=auth_headers,
            json={"content": "최신 요약을 알려주세요", "max_messages": 5}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["assistant_message"]["content"]
    assert data["artifact"]["id"] is not None

    structured_kwargs = mock_structured.generate_structured_report.call_args.kwargs
    expected_prompt = f"{topic.prompt_user}\n\n{topic.prompt_system}"
    assert structured_kwargs["system_prompt"] == expected_prompt
    assert mock_structured.generate_structured_report.call_count == 1


@pytest.mark.api
def test_tc_008_ask_returns_400_when_prompts_missing(
    client,
    auth_headers,
    create_test_user
):
    """TC-008: ask() must reject topics without prompt_user/system information."""
    topic = TopicDB.create_topic(
        user_id=create_test_user.id,
        topic_data=TopicCreate(
            input_prompt="설정되지 않은 토픽",
            language="ko",
            source_type=TopicSourceType.BASIC,
            prompt_user=None,
            prompt_system=None
        )
    )

    response = client.post(
        f"/api/topics/{topic.id}/ask",
        headers=auth_headers,
        json={"content": "프롬프트 상태 점검"}
    )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION.REQUIRED_FIELD"
    assert body["error"]["message"] == "이 토픽의 프롬프트가 설정되어 있지 않습니다."
    assert "POST /api/topics/plan으로 계획을 먼저 생성해주세요." in body["error"]["hint"]


def test_tc_009_background_generation_uses_composed_prompt(tmp_path, monkeypatch):
    """TC-009: _background_generate_report() should use composed prompt and mark artifact completed."""
    topic_id = 901
    artifact_id = 4501
    env = _setup_background_env(
        monkeypatch,
        tmp_path,
        topic_id=topic_id,
        artifact_id=artifact_id,
        prompt_user="Step 1 from plan",
        prompt_system="Rules: format check"
    )

    structured_response = _make_structured_response()

    with patch("app.routers.topics.StructuredClaudeClient") as mock_structured_cls, \
            patch("app.routers.topics.ClaudeClient") as mock_claude_cls:
        mock_structured = MagicMock()
        mock_structured.generate_structured_report.return_value = structured_response
        mock_structured_cls.return_value = mock_structured

        mock_claude = MagicMock()
        mock_claude.model = "claude-3"
        mock_claude.last_input_tokens = 0
        mock_claude.last_output_tokens = 0
        mock_claude_cls.return_value = mock_claude

        asyncio.run(
            topics_module._background_generate_report(
                topic_id=topic_id,
                artifact_id=artifact_id,
                topic="AI 시장",
                plan="# 계획",
                template_id=None,
                user_id="1",
                is_web_search=False
            )
        )

    completed_calls = [
        call for call in env.update_mock.call_args_list
        if call.kwargs.get("status") == topics_module.ARTIFACT_STATUS_COMPLETED
    ]
    assert completed_calls, "Artifact status was never marked completed"
    assert completed_calls[-1].kwargs.get("progress_percent") == 100

    structured_kwargs = mock_structured.generate_structured_report.call_args.kwargs
    assert structured_kwargs["system_prompt"] == "Step 1 from plan\n\nRules: format check"


def test_tc_010_background_generation_fallbacks_to_default_prompt(tmp_path, monkeypatch, caplog):
    """TC-010: _background_generate_report() should call get_system_prompt when topic prompts are missing."""
    topic_id = 902
    artifact_id = 4502
    env = _setup_background_env(
        monkeypatch,
        tmp_path,
        topic_id=topic_id,
        artifact_id=artifact_id,
        prompt_user=None,
        prompt_system=None,
        template_id=1
    )

    structured_response = _make_structured_response()
    fallback_prompt = "Default system prompt"

    monkeypatch.setattr(
        "app.routers.topics.get_system_prompt",
        lambda **kwargs: fallback_prompt
    )
    caplog.set_level(logging.WARNING, logger="app.routers.topics")

    with patch("app.routers.topics.StructuredClaudeClient") as mock_structured_cls, \
            patch("app.routers.topics.ClaudeClient") as mock_claude_cls:
        mock_structured = MagicMock()
        mock_structured.generate_structured_report.return_value = structured_response
        mock_structured_cls.return_value = mock_structured

        mock_claude = MagicMock()
        mock_claude.model = "claude-3"
        mock_claude.last_input_tokens = 0
        mock_claude.last_output_tokens = 0
        mock_claude_cls.return_value = mock_claude

        asyncio.run(
            topics_module._background_generate_report(
                topic_id=topic_id,
                artifact_id=artifact_id,
                topic="AI 시장",
                plan="# 계획",
                template_id=1,
                user_id="2",
                is_web_search=False
            )
        )

    assert any("both NULL" in record.message for record in caplog.records), \
        "Expected warning about missing prompts"
    completed_calls = [
        call for call in env.update_mock.call_args_list
        if call.kwargs.get("status") == topics_module.ARTIFACT_STATUS_COMPLETED
    ]
    assert completed_calls

    structured_kwargs = mock_structured.generate_structured_report.call_args.kwargs
    assert structured_kwargs["system_prompt"] == fallback_prompt
