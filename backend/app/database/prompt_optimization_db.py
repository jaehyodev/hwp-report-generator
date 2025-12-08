"""프롬프트 고도화 결과 CRUD 모듈."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from app.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class PromptOptimizationDB:
    """prompt_optimization_result 테이블 CRUD 유틸리티."""

    @staticmethod
    def create(
        topic_id: int,
        user_id: int,
        user_prompt: str,
        hidden_intent: Optional[str],
        role: str,
        context: str,
        task: str,
        model_name: str,
        latency_ms: int,
        emotional_needs: Optional[Dict[str, Any]] = None,
        underlying_purpose: Optional[str] = None,
        formality: Optional[str] = None,
        confidence_level: Optional[str] = None,
        decision_focus: Optional[str] = None,
        output_format: Optional[str] = None,
        original_topic: Optional[str] = None,
    ) -> int:
        """새 고도화 결과를 저장한다.

        경로:
            backend/app/database/prompt_optimization_db.py::PromptOptimizationDB.create()

        설명:
            사용자 고도화 요청 및 Claude의 분석 결과를 DB에 저장합니다.

        파라미터:
            topic_id: 토픽 ID
            user_id: 사용자 ID
            user_prompt: 사용자 입력 프롬프트
            hidden_intent: 숨겨진 의도
            role: Claude용 역할 프롬프트
            context: Claude용 컨텍스트 문자열
            task: Claude용 작업 설명
            model_name: 사용한 모델명
            latency_ms: 응답 시간 (ms)
            emotional_needs: 감정적 니즈(dict) - JSON 문자열로 저장
            underlying_purpose: 근본 목적
            formality: 형식성 (formal, neutral, casual)
            confidence_level: 확신 수준 (high, medium, low)
            decision_focus: 결정 초점 (decisive, exploratory, uncertain)
            output_format: Claude 응답 구조 정보 (str)
            original_topic: 사용자 원본 입력 주제 (str)

        반환:
            생성된 레코드 ID

        에러:
            sqlite3.OperationalError: DB 명령 실행 실패 시
            sqlite3.IntegrityError: 무결성 제약 조건 위반 시
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now()

        def _to_text(value: Any) -> Optional[str]:
            """dict/list는 JSON 문자열로, 나머지는 문자열 캐스팅."""
            if value is None:
                return None
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        emotional_needs_payload: Optional[str] = None
        if emotional_needs is not None:
            if isinstance(emotional_needs, str):
                emotional_needs_payload = emotional_needs
            else:
                emotional_needs_payload = json.dumps(emotional_needs, ensure_ascii=False)
        
        output_format_needs_payload: Optional[str] = None
        if output_format is not None:
            if isinstance(output_format, str):
                output_format_needs_payload = output_format
            else:
                output_format_needs_payload = json.dumps(output_format, ensure_ascii=False)

        hidden_intent_value = _to_text(hidden_intent)
        underlying_purpose_value = _to_text(underlying_purpose)
        role_value = _to_text(role) or ""
        context_value = _to_text(context) or ""
        task_value = _to_text(task) or ""
        model_name_value = _to_text(model_name) or ""
        user_prompt_value = _to_text(user_prompt) or ""

        formality_value = formality or (emotional_needs.get("formality") if isinstance(emotional_needs, dict) else None)
        confidence_value = confidence_level or (
            emotional_needs.get("confidence_level") if isinstance(emotional_needs, dict) else None
        )
        decision_value = decision_focus or (
            emotional_needs.get("decision_focus") if isinstance(emotional_needs, dict) else None
        )

        try:
            # prompt_optimization_result 테이블에 신규 레코드를 INSERT
            cursor.execute(
                """
                INSERT INTO prompt_optimization_result (
                    topic_id,
                    user_id,
                    user_prompt,
                    hidden_intent,
                    emotional_needs,
                    underlying_purpose,
                    formality,
                    confidence_level,
                    decision_focus,
                    output_format,
                    original_topic,
                    role,
                    context,
                    task,
                    model_name,
                    latency_ms,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic_id,
                    user_id,
                    user_prompt_value,
                    hidden_intent_value,
                    emotional_needs_payload,
                    underlying_purpose_value,
                    formality_value,
                    confidence_value,
                    decision_value,
                    output_format_needs_payload,
                    original_topic or None,
                    role_value,
                    context_value,
                    task_value,
                    model_name_value,
                    latency_ms,
                    now,
                    now,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            conn.rollback()
            logger.exception("프롬프트 고도화 결과 저장 실패")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_latest_by_topic(topic_id: int) -> Optional[Dict[str, Any]]:
        """토픽 기준 최신 고도화 결과를 조회한다.

        경로:
            backend/app/database/prompt_optimization_db.py::PromptOptimizationDB.get_latest_by_topic()

        설명:
            특정 토픽의 가장 최근 고도화 결과를 반환합니다. (created_at DESC)

        파라미터:
            topic_id: 토픽 ID

        반환:
            최신 레코드 딕셔너리 또는 None (결과 없을 시)

        에러:
            sqlite3.OperationalError: 조회 쿼리 실패 시
            sqlite3.IntegrityError: 무결성 제약 조건 발생 시
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # created_at 내림차순으로 최신 레코드를 1건 조회
            cursor.execute(
                """
                SELECT *
                FROM prompt_optimization_result
                WHERE topic_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (topic_id,),
            )
            row = cursor.fetchone()
            return PromptOptimizationDB._row_to_dict(row) if row else None
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            logger.exception("토픽별 최신 고도화 결과 조회 실패")
            raise
        finally:
            conn.close()

    @staticmethod
    def update(
        record_id: int,
        role: Optional[str] = None,
        context: Optional[str] = None,
        task: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> bool:
        """특정 고도화 결과를 부분 업데이트한다.

        경로:
            backend/app/database/prompt_optimization_db.py::PromptOptimizationDB.update()

        설명:
            기존 고도화 결과의 role, context, task, model_name만 수정 가능합니다.
            user_prompt는 수정 불가하며, updated_at은 자동 갱신됩니다.

        파라미터:
            record_id: 수정할 레코드 ID
            role: 새로운 역할 프롬프트 (선택)
            context: 새로운 컨텍스트 (선택)
            task: 새로운 작업 문구 (선택)
            model_name: 모델명 변경 값 (선택)

        반환:
            업데이트 성공 여부 (bool)

        에러:
            sqlite3.OperationalError: UPDATE 실행 실패 시
            sqlite3.IntegrityError: 무결성 제약 조건 위반 시
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        fields = []
        params = []

        if role is not None:
            fields.append("role = ?")
            params.append(role)
        if context is not None:
            fields.append("context = ?")
            params.append(context)
        if task is not None:
            fields.append("task = ?")
            params.append(task)
        if model_name is not None:
            fields.append("model_name = ?")
            params.append(model_name)

        if not fields:
            return False

        params.append(datetime.now())
        params.append(record_id)

        try:
            # 선택된 칼럼만 SET 하고 updated_at을 갱신하는 UPDATE
            cursor.execute(
                f"""
                UPDATE prompt_optimization_result
                SET {', '.join(fields)}, updated_at = ?
                WHERE id = ?
                """,
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount > 0
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            conn.rollback()
            logger.exception("프롬프트 고도화 결과 업데이트 실패")
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_by_topic(topic_id: int) -> int:
        """특정 토픽의 고도화 결과를 모두 삭제한다.

        경로:
            backend/app/database/prompt_optimization_db.py::PromptOptimizationDB.delete_by_topic()

        설명:
            CASCADE 외래키로 인해 토픽 삭제 시 자동 호출될 수도 있습니다.
            명시적 삭제 시에도 사용됩니다.

        파라미터:
            topic_id: 토픽 ID

        반환:
            삭제된 행 수

        에러:
            sqlite3.OperationalError: DELETE 실행 실패 시
            sqlite3.IntegrityError: 무결성 제약 조건 발생 시
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 동일 topic_id에 해당하는 모든 레코드를 삭제
            cursor.execute(
                "DELETE FROM prompt_optimization_result WHERE topic_id = ?",
                (topic_id,),
            )
            conn.commit()
            return cursor.rowcount
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            conn.rollback()
            logger.exception("프롬프트 고도화 결과 삭제 실패")
            raise
        finally:
            conn.close()

    @staticmethod
    def get_by_id(record_id: int) -> Optional[Dict[str, Any]]:
        """ID로 단건 프롬프트 고도화 결과를 조회한다.

        경로:
            backend/app/database/prompt_optimization_db.py::PromptOptimizationDB.get_by_id()

        설명:
            단일 고도화 결과 레코드를 기본 키(id)로 조회합니다.

        파라미터:
            record_id: 조회할 레코드 ID

        반환:
            레코드 딕셔너리 또는 None (없을 시)

        에러:
            sqlite3.OperationalError: SELECT 실행 실패 시
            sqlite3.IntegrityError: 무결성 제약 조건 발생 시
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 기본 키로 단일 레코드를 조회
            cursor.execute(
                "SELECT * FROM prompt_optimization_result WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            return PromptOptimizationDB._row_to_dict(row) if row else None
        except (sqlite3.OperationalError, sqlite3.IntegrityError):
            logger.exception("프롬프트 고도화 결과 단건 조회 실패")
            raise
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """sqlite3.Row 객체를 dict로 변환한다."""
        data = dict(row)
        return data
