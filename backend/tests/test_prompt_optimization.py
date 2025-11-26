"""프롬프트 고도화 전체 흐름 테스트 모음.

이 모듈은 prompt_optimization_result 테이블을 이용하는 DB CRUD, Claude
프롬프트 최적화 유틸리티, Pydantic 모델, FastAPI 라우터를 통합적으로 검증한다.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from app.database.connection import get_db_connection
from app.database.prompt_optimization_db import PromptOptimizationDB
from app.database.topic_db import TopicDB
from app.models.prompt_optimization import (
    PromptOptimizationCreate,
    PromptOptimizationResponse,
    PromptOptimizationUpdate,
)
from app.models.topic import TopicCreate
from app.utils import prompt_optimizer
from app.utils.prompt_optimizer import map_optimized_to_claude_payload


# ---------------------------------------------------------------------------
# 공용 픽스처 & 헬퍼
# ---------------------------------------------------------------------------


@pytest.fixture
def topic_factory(create_test_user):
    """테스트 토픽을 손쉽게 생성하기 위한 헬퍼."""

    def _create_topic(owner=None, prompt: str = "AI 리포트 샘플"):
        user = owner or create_test_user
        return TopicDB.create_topic(
            user_id=user.id,
            topic_data=TopicCreate(input_prompt=prompt, language="ko"),
        )

    return _create_topic


def _create_sample_optimization(
    *,
    topic_id: int,
    user_id: int,
    role: str = "시니어 분석가",
    context: str = "금융 시장",
    task: str = "요청 정리",
    model_name: str = "claude-sonnet-4-5-20250929",
    latency_ms: int = 120,
    hidden_intent: Optional[str] = "시장 점유율 확대",
) -> int:
    """DB에 프롬프트 고도화 레코드를 하나 만들고 ID를 반환한다."""

    return PromptOptimizationDB.create(
        topic_id=topic_id,
        user_id=user_id,
        user_prompt="우리 조직의 시장 전략을 자세히 분석하고 개선안을 제시해줘.",
        hidden_intent=hidden_intent,
        emotional_needs={"tone": "formal", "urgency": "high"},
        underlying_purpose="경영진 보고",
        role=role,
        context=context,
        task=task,
        model_name=model_name,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# TC-001 ~ TC-005: PromptOptimizationDB CRUD 테스트
# ---------------------------------------------------------------------------


@pytest.mark.db
class TestPromptOptimizationDB:
    """prompt_optimization_result 테이블 CRUD 검증."""

    def test_prompt_optimization_db_create_inserts_record(
        self,
        test_db,
        create_test_user,
        topic_factory,
    ) -> None:
        """TC-001: PromptOptimizationDB.create() 신규 레코드 생성."""

        # 테스트 토픽 및 사용자 준비
        topic = topic_factory()

        # 레코드 생성 실행
        record_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id)

        # DB에서 직접 조회하여 저장된 값 검증
        stored = PromptOptimizationDB.get_by_id(record_id)
        assert stored is not None, "레코드가 생성되어야 한다."
        assert stored["topic_id"] == topic.id
        assert stored["user_prompt"].startswith("우리 조직")
        assert json.loads(stored["emotional_needs"]) == {"tone": "formal", "urgency": "high"}

    def test_prompt_optimization_db_get_latest_returns_newest(
        self,
        test_db,
        create_test_user,
        topic_factory,
    ) -> None:
        """TC-002: PromptOptimizationDB.get_latest_by_topic() 최신 결과 조회."""

        # 동일 토픽에 2건을 넣고 created_at을 조정하여 최신값을 확인
        topic = topic_factory(prompt="최신 결과 검증")
        older_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id, task="첫 번째")
        newest_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id, task="두 번째")

        # older_id의 created_at을 과거로 돌려 최신 정렬 보장
        connection = get_db_connection()
        connection.execute(
            "UPDATE prompt_optimization_result SET created_at = ? WHERE id = ?",
            (datetime.now() - timedelta(days=1), older_id),
        )
        connection.commit()
        connection.close()

        latest = PromptOptimizationDB.get_latest_by_topic(topic.id)
        assert latest is not None, "최신 결과가 존재해야 한다."
        assert latest["id"] == newest_id
        assert latest["task"] == "두 번째"

    def test_prompt_optimization_db_update_modifies_partial_fields(
        self,
        test_db,
        create_test_user,
        topic_factory,
    ) -> None:
        """TC-003: PromptOptimizationDB.update() 부분 업데이트 확인."""

        # 기존 레코드 생성 후 role/context를 수정하여 업데이트 로직 검증
        topic = topic_factory(prompt="부분 업데이트 시나리오")
        record_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id)
        before = PromptOptimizationDB.get_by_id(record_id)

        updated = PromptOptimizationDB.update(
            record_id,
            role="수석 컨설턴트",
            context="국내 은행권",
            model_name="claude-opus-202510",
        )

        after = PromptOptimizationDB.get_by_id(record_id)
        assert updated is True
        assert after["role"] == "수석 컨설턴트"
        assert after["context"] == "국내 은행권"
        assert after["task"] == before["task"], "task는 유지되어야 한다."
        assert after["model_name"] == "claude-opus-202510"

    def test_prompt_optimization_db_delete_by_topic_removes_rows(
        self,
        test_db,
        create_test_user,
        topic_factory,
    ) -> None:
        """TC-004: PromptOptimizationDB.delete_by_topic() 토픽별 삭제."""

        # 동일 토픽 2건, 다른 토픽 1건을 만들어 삭제 영향 범위를 확인
        topic = topic_factory(prompt="삭제 검증")
        another_topic = topic_factory(prompt="삭제 대상 아님")
        first_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id)
        second_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id)
        _create_sample_optimization(topic_id=another_topic.id, user_id=create_test_user.id)

        deleted = PromptOptimizationDB.delete_by_topic(topic.id)
        assert deleted == 2, "해당 토픽의 2건만 삭제되어야 한다."
        assert PromptOptimizationDB.get_by_id(first_id) is None
        assert PromptOptimizationDB.get_by_id(second_id) is None

    def test_prompt_optimization_db_get_by_id_returns_single_record(
        self,
        test_db,
        create_test_user,
        topic_factory,
    ) -> None:
        """TC-005: PromptOptimizationDB.get_by_id() 단건 조회."""

        # 생성된 레코드를 ID로 조회했을 때 필드가 그대로 노출되는지 확인
        topic = topic_factory(prompt="단건 조회")
        record_id = _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id)

        record = PromptOptimizationDB.get_by_id(record_id)
        assert record is not None
        assert record["id"] == record_id
        assert record["topic_id"] == topic.id
        assert record["hidden_intent"] == "시장 점유율 확대"


# ---------------------------------------------------------------------------
# TC-006 ~ TC-008: 프롬프트 최적화 로직
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPromptOptimizer:
    """Claude 최적화 헬퍼 테스트."""

    @pytest.mark.asyncio
    async def test_optimize_prompt_with_claude_returns_payload(self, monkeypatch):
        """TC-006: optimize_prompt_with_claude() 정상 호출 (Mocking 필수)."""

        # ClaudeClient를 Stub으로 교체하여 JSON 응답을 강제로 반환
        sample_response = {
            "hidden_intent": "고객 이탈 방지",
            "emotional_needs": {"tone": "warm"},
            "underlying_purpose": "전략 고도화",
            "role": "AI 전략 분석가",
            "context": "리테일 금융",
            "task": "시장 동향과 개선안을 정리",
        }

        def _fake_create(**_: Any) -> Any:
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(sample_response))])

        class DummyClaude:
            def __init__(self) -> None:
                self.client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

        monkeypatch.setattr(prompt_optimizer, "ClaudeClient", DummyClaude)

        result = await prompt_optimizer.optimize_prompt_with_claude(
            user_prompt="우리 고객의 요구를 분석해줘",
            topic_id=1,
            model="claude-sonnet-4-5-20250929",
        )

        assert result["hidden_intent"] == "고객 이탈 방지"
        assert result["emotional_needs"] == {"tone": "warm"}
        assert result["role"] == "AI 전략 분석가"
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_optimize_prompt_with_claude_handles_timeout(self, monkeypatch):
        """TC-007: optimize_prompt_with_claude() Timeout 처리."""

        # 호출이 asyncio.TimeoutError를 던지도록 wait_for를 패치
        async def _fake_wait_for(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
            raise asyncio.TimeoutError()

        class DummyClaude:  # pragma: no cover - 초기화만 필요
            def __init__(self) -> None:
                self.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: MagicMock()))

        monkeypatch.setattr(prompt_optimizer.asyncio, "wait_for", _fake_wait_for)
        monkeypatch.setattr(prompt_optimizer, "ClaudeClient", DummyClaude)

        with pytest.raises(TimeoutError):
            await prompt_optimizer.optimize_prompt_with_claude(
                user_prompt="지연 시나리오",
                topic_id=99,
                model="claude-sonnet-4-5-20250929",
            )

    def test_map_optimized_to_claude_payload_transforms_response(self):
        """TC-008: map_optimized_to_claude_payload() Payload 변환."""

        # PromptOptimizationResponse를 Claude payload 형태로 변환하는 로직 검증
        now = datetime.utcnow()
        response_model = PromptOptimizationResponse(
            id=1,
            topic_id=10,
            user_id=5,
            user_prompt="시장 전략",
            hidden_intent="수익성 극대화",
            emotional_needs={"tone": "formal"},
            underlying_purpose="경영진 보고",
            role="AI 애널리스트",
            context="국내 시장",
            task="상세 전략을 제안",
            model_name="claude-sonnet-4-5-20250929",
            latency_ms=333,
            created_at=now,
            updated_at=now,
        )

        payload = map_optimized_to_claude_payload(
            optimization_result=response_model,
            original_user_prompt="고객 유지 전략을 추천해줘",
            model="claude-opus-202510",
        )

        assert payload["model"] == "claude-opus-202510"
        assert "# CONTEXT" in payload["system"]
        assert "원래 요청" in payload["messages"][0]["content"]
        assert payload["temperature"] == 0.1


# ---------------------------------------------------------------------------
# TC-009 ~ TC-010: Pydantic 모델 검증
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModels:
    """PromptOptimization 관련 모델 유효성 검사."""

    def test_prompt_optimization_create_accepts_valid_payload(self):
        """TC-009: PromptOptimizationCreate 유효성 검증."""

        # 필수 필드를 모두 채워 정상적으로 모델이 생성되는지 확인
        payload = PromptOptimizationCreate(
            user_prompt="2025년 AI 산업 전망을 심층 분석해줘",
            hidden_intent="시장 우위 확보",
            emotional_needs={"tone": "confident"},
            underlying_purpose="투자 보고",
            role="전략 컨설턴트",
            context="국내 스타트업",
            task="리스크와 기회를 정리",
            model_name="claude-opus-202510",
            latency_ms=512,
        )

        assert payload.user_prompt.startswith("2025년 AI")
        assert payload.role == "전략 컨설턴트"
        assert payload.model_name == "claude-opus-202510"
        assert payload.latency_ms == 512

    def test_prompt_optimization_update_allows_partial_fields(self):
        """TC-010: PromptOptimizationUpdate 부분 업데이트 필드만 허용."""

        # 일부 필드만 채워도 모델이 생성되고 dump 결과에 동일 필드만 포함되는지 확인
        update_model = PromptOptimizationUpdate(
            role="프롬프트 엔지니어",
            task="고객 요청 포맷 정리",
        )

        dumped = update_model.model_dump(exclude_none=True)
        assert set(dumped.keys()) == {"role", "task"}

        # 역할/컨텍스트/작업 중 하나라도 비어 있으면 ValueError가 발생해야 함
        with pytest.raises(ValueError):
            map_optimized_to_claude_payload(  # type: ignore[arg-type]
                optimization_result=PromptOptimizationResponse(
                    id=1,
                    topic_id=1,
                    user_id=1,
                    user_prompt="dummy prompt",
                    hidden_intent=None,
                    emotional_needs=None,
                    underlying_purpose=None,
                    role="",
                    context="",
                    task="",
                    model_name="claude-sonnet-4-5-20250929",
                    latency_ms=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ),
                original_user_prompt="원본 요청",
            )


# ---------------------------------------------------------------------------
# TC-011 ~ TC-015: API 엔드포인트 통합 테스트
# ---------------------------------------------------------------------------


@pytest.mark.api
class TestPromptOptimizationAPI:
    """FastAPI Topics 라우터의 프롬프트 고도화 엔드포인트 테스트."""

    def test_post_optimize_prompt_success(
        self,
        client,
        auth_headers,
        create_test_user,
        topic_factory,
        monkeypatch,
    ) -> None:
        """TC-011: POST /api/topics/{id}/optimize-prompt 정상 요청."""

        # 토픽 생성 후 Claude 호출을 Mock하여 항상 동일한 결과를 반환
        topic = topic_factory()

        async def _fake_optimize(*_, **__):
            return {
                "hidden_intent": "고객 성공",
                "emotional_needs": {"tone": "warm"},
                "underlying_purpose": "전략 보고",
                "role": "시니어 어드바이저",
                "context": "금융",
                "task": "거버넌스 점검",
                "latency_ms": 77,
            }

        monkeypatch.setattr("app.routers.topics.optimize_prompt_with_claude", _fake_optimize)

        response = client.post(
            f"/api/topics/{topic.id}/optimize-prompt",
            headers=auth_headers,
            json={"user_prompt": "우리 고객 만족도를 높이는 방안을 알려줘"},
        )

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["data"]["topic_id"] == topic.id
        assert body["data"]["role"] == "시니어 어드바이저"

    def test_post_optimize_prompt_topic_not_found(self, client, auth_headers) -> None:
        """TC-012: POST /api/topics/{id}/optimize-prompt - Topic 없음 (404)."""

        # 존재하지 않는 토픽 ID로 호출
        response = client.post(
            "/api/topics/999999/optimize-prompt",
            headers=auth_headers,
            json={"user_prompt": "없는 토픽"},
        )

        body = response.json()
        assert response.status_code == 404
        assert body["error"]["code"] == "TOPIC.NOT_FOUND"

    def test_post_optimize_prompt_forbidden(self, client, auth_headers, create_test_admin, topic_factory) -> None:
        """TC-013: POST /api/topics/{id}/optimize-prompt - 권한 없음 (403)."""

        # 관리자 계정으로 토픽을 만든 뒤 다른 사용자가 접근하게 하여 권한 오류 검증
        admin_topic = topic_factory(owner=create_test_admin, prompt="권한 테스트")
        response = client.post(
            f"/api/topics/{admin_topic.id}/optimize-prompt",
            headers=auth_headers,
            json={"user_prompt": "접근 차단"},
        )

        body = response.json()
        assert response.status_code == 403
        assert body["error"]["code"] == "TOPIC.UNAUTHORIZED"

    def test_get_optimization_result_returns_payload(
        self,
        client,
        auth_headers,
        create_test_user,
        topic_factory,
    ) -> None:
        """TC-014: GET /api/topics/{id}/optimization-result - 결과 있음."""

        # 사전 DB에 결과를 넣고 GET 호출 시 data가 채워지는지 확인
        topic = topic_factory()
        _create_sample_optimization(topic_id=topic.id, user_id=create_test_user.id)

        response = client.get(
            f"/api/topics/{topic.id}/optimization-result",
            headers=auth_headers,
        )

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["data"]["topic_id"] == topic.id
        assert body["data"]["role"] == "시니어 분석가"

    def test_get_optimization_result_returns_none(self, client, auth_headers, topic_factory) -> None:
        """TC-015: GET /api/topics/{id}/optimization-result - 결과 없음."""

        # 토픽만 존재하고 결과가 없을 때 data=None 이어야 함
        topic = topic_factory(prompt="결과 없음")
        response = client.get(
            f"/api/topics/{topic.id}/optimization-result",
            headers=auth_headers,
        )

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["data"] is None
