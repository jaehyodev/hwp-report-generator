"""테스트: Placeholders 테이블 Sort 컬럼 기능.

Spec: backend/doc/specs/20251128_placeholders_sort_column.md
Date: 2025-11-28
"""

import pytest
from datetime import datetime
from app.database.template_db import TemplateDB, PlaceholderDB
from app.database.connection import get_db_connection
from app.models.template import Placeholder, TemplateCreate


class TestPlaceholdersSortSchema:
    """TC-001: DB 스키마 검증 - Sort 컬럼 확인"""

    def test_placeholder_sort_column_exists(self):
        """placeholders 테이블에 sort 컬럼이 존재하고 속성이 올바른지 확인."""
        conn = get_db_connection()
        cursor = conn.cursor()

        # PRAGMA table_info로 컬럼 정보 조회
        cursor.execute("PRAGMA table_info(placeholders)")
        columns = {col[1]: col for col in cursor.fetchall()}
        conn.close()

        # 필수 체크: sort 컬럼 존재
        assert "sort" in columns, "sort 컬럼이 존재하지 않음"

        sort_info = columns["sort"]
        # (cid, name, type, notnull, dflt_value, pk)
        assert sort_info[2] == "INTEGER", "sort 컬럼 타입은 INTEGER여야 함"
        assert sort_info[3] == 1, "sort 컬럼은 NOT NULL이어야 함"
        assert sort_info[4] == "0", "sort 컬럼 기본값은 0이어야 함"


class TestPlaceholdersBatchInsert:
    """TC-002: PlaceholderDB.create_placeholders_batch - Sort 값 저장 확인"""

    def test_create_placeholders_batch_with_sort(self):
        """배치 INSERT 시 sort 값이 순차적으로 저장되는지 확인."""
        template_id = 99  # 테스트용 ID
        placeholder_list = ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}"]

        # Batch 생성
        placeholders = PlaceholderDB.create_placeholders_batch(template_id, placeholder_list)

        # 검증
        assert len(placeholders) == 3, "3개의 placeholder가 생성되어야 함"
        assert placeholders[0].sort == 0, f"첫 번째 sort는 0이어야 함, 실제: {placeholders[0].sort}"
        assert placeholders[1].sort == 1, f"두 번째 sort는 1이어야 함, 실제: {placeholders[1].sort}"
        assert placeholders[2].sort == 2, f"세 번째 sort는 2여야 함, 실제: {placeholders[2].sort}"

        # 키도 확인
        assert placeholders[0].placeholder_key == "{{TITLE}}"
        assert placeholders[1].placeholder_key == "{{SUMMARY}}"
        assert placeholders[2].placeholder_key == "{{BACKGROUND}}"


class TestPlaceholdersOrderBySort:
    """TC-003: get_placeholders_by_template - Sort 순서 조회 확인"""

    def test_get_placeholders_by_template_ordered_by_sort(self):
        """조회 시 placeholder가 sort 순서로 정렬되어 반환되는지 확인."""
        template_id = 100  # 테스트용 ID
        placeholder_list = ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}"]

        # Batch 생성
        PlaceholderDB.create_placeholders_batch(template_id, placeholder_list)

        # 조회
        placeholders = PlaceholderDB.get_placeholders_by_template(template_id)

        # Sort 순서 검증
        assert len(placeholders) == 3, "3개의 placeholder가 조회되어야 함"
        sort_values = [p.sort for p in placeholders]
        assert sort_values == [0, 1, 2], f"Sort 순서가 [0, 1, 2]여야 함, 실제: {sort_values}"

        # 키 순서 검증
        keys = [p.placeholder_key for p in placeholders]
        assert keys == ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}"], f"키 순서 오류: {keys}"


class TestPlaceholderModel:
    """TC-005: Placeholder 모델 - Sort 필드 포함 확인"""

    def test_placeholder_model_has_sort_field(self):
        """Placeholder 모델에 sort 필드가 포함되었고 정상적으로 작동하는지 확인."""
        now = datetime.now()
        placeholder = Placeholder(
            id=1,
            template_id=1,
            placeholder_key="{{TITLE}}",
            sort=0,
            created_at=now
        )

        # 필드 존재 확인
        assert hasattr(placeholder, "sort"), "Placeholder에 sort 필드가 없음"
        assert placeholder.sort == 0, f"sort 값이 0이어야 함, 실제: {placeholder.sort}"

        # JSON 직렬화 확인
        model_dict = placeholder.model_dump()
        assert "sort" in model_dict, "model_dump()에 sort 필드가 없음"
        assert model_dict["sort"] == 0, f"직렬화된 sort 값이 0이어야 함, 실제: {model_dict['sort']}"

    def test_placeholder_model_sort_default(self):
        """Placeholder 모델의 sort 필드 기본값이 0인지 확인."""
        now = datetime.now()
        placeholder = Placeholder(
            id=1,
            template_id=1,
            placeholder_key="{{TITLE}}",
            # sort를 지정하지 않으면 기본값 0
            created_at=now
        )

        assert placeholder.sort == 0, "sort의 기본값은 0이어야 함"


class TestPlaceholderRowMapping:
    """TC-006: 기존 데이터 호환성 - Sort NULL/DEFAULT 처리"""

    def test_placeholder_sort_default_when_none(self):
        """_row_to_placeholder에서 sort=None인 경우 0으로 처리되는지 확인."""
        # DB 행 형식: (id, template_id, placeholder_key, sort, created_at)
        now = datetime.now().isoformat()
        row = (1, 1, "{{TITLE}}", None, now)  # sort=None

        placeholder = PlaceholderDB._row_to_placeholder(row)

        assert placeholder is not None, "placeholder가 None이 아니어야 함"
        assert placeholder.sort == 0, f"sort=None일 때 기본값 0으로 처리되어야 함, 실제: {placeholder.sort}"

    def test_placeholder_sort_value_preserved(self):
        """_row_to_placeholder에서 sort 값이 정상적으로 보존되는지 확인."""
        now = datetime.now().isoformat()
        row = (1, 1, "{{TITLE}}", 5, now)  # sort=5

        placeholder = PlaceholderDB._row_to_placeholder(row)

        assert placeholder.sort == 5, f"sort 값이 5여야 함, 실제: {placeholder.sort}"


class TestPlaceholderCreateModel:
    """추가: PlaceholderCreate 모델 - Sort 필드 선택사항 확인"""

    def test_placeholder_create_model_sort_optional(self):
        """PlaceholderCreate 모델에서 sort가 선택사항인지 확인."""
        from app.models.template import PlaceholderCreate

        # sort 없이 생성 (선택사항이므로 가능)
        pc = PlaceholderCreate(
            template_id=1,
            placeholder_key="{{TITLE}}"
        )
        assert pc.sort is None, "sort가 지정되지 않으면 None이어야 함"

        # sort와 함께 생성
        pc2 = PlaceholderCreate(
            template_id=1,
            placeholder_key="{{TITLE}}",
            sort=0
        )
        assert pc2.sort == 0, "sort가 지정되면 그 값이 유지되어야 함"


class TestPlaceholderEmptyList:
    """추가: 엣지 케이스 - 빈 리스트 처리"""

    def test_create_placeholders_batch_empty_list(self):
        """placeholder_list가 비어있을 때 정상적으로 처리되는지 확인."""
        template_id = 101
        placeholder_list = []

        placeholders = PlaceholderDB.create_placeholders_batch(template_id, placeholder_list)

        assert placeholders == [], "빈 리스트 반환되어야 함"


class TestPlaceholderSingleItem:
    """추가: 엣지 케이스 - 단일 항목 처리"""

    def test_create_placeholders_batch_single_item(self):
        """placeholder_list에 1개의 항목만 있을 때 sort=0으로 저장되는지 확인."""
        template_id = 102
        placeholder_list = ["{{TITLE}}"]

        placeholders = PlaceholderDB.create_placeholders_batch(template_id, placeholder_list)

        assert len(placeholders) == 1, "1개의 placeholder가 생성되어야 함"
        assert placeholders[0].sort == 0, "유일한 항목의 sort는 0이어야 함"
        assert placeholders[0].placeholder_key == "{{TITLE}}"
