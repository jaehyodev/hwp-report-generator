"""
Unit tests for Artifact state management (v2.5+ Option A).

Tests comprehensive state tracking functionality:
- Artifact creation with NULL file_path (scheduled state)
- Progressive status updates without file information
- File information addition at completion
- Error state handling
- Backward compatibility (existing artifacts with completed status)
"""
import pytest
import sqlite3
import os
from datetime import datetime
from pathlib import Path

from app.database.artifact_db import ArtifactDB
from app.database.connection import get_db_connection, init_db, DB_PATH
from app.models.artifact import ArtifactCreate, Artifact
from shared.types.enums import ArtifactKind
from shared.constants import ProjectPath


class TestArtifactStateManagement:
    """Test suite for Artifact state management functionality (v2.5+ Option A)."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Setup test database before each test."""
        # Force test database path by mocking DB_PATH
        test_db_path = str(ProjectPath.DATABASE_DIR / "test_artifact_state.db")

        # Remove if exists
        if Path(test_db_path).exists():
            Path(test_db_path).unlink()

        # Mock the DB_PATH in connection module
        import app.database.connection as conn_module
        monkeypatch.setattr(conn_module, "DB_PATH", test_db_path)

        # Initialize with schema
        init_db()
        yield
        # Cleanup
        if Path(test_db_path).exists():
            Path(test_db_path).unlink()

    # ============================================================================
    # TC-DB-001: Create Artifact with status="scheduled" and file_path=NULL
    # ============================================================================
    def test_create_artifact_with_scheduled_status_null_file_path(self):
        """
        TC-DB-001: Artifact 생성 시 status="scheduled", file_path=NULL로 즉시 생성 가능해야 함.

        목적: 작업 시작 직후 파일 없이도 Artifact를 생성하고 상태 추적 시작 가능함을 검증.
        """
        started_at = datetime.now().isoformat()

        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            locale="ko",
            version=1,
            filename="report.md",
            file_path=None,  # ✅ NULL during work
            file_size=0,
            status="scheduled",  # ✅ Scheduled state
            progress_percent=0,
            started_at=started_at
        )

        # Create artifact (simulating /generate immediate creation)
        artifact = ArtifactDB.create_artifact(
            topic_id=1,
            message_id=1,
            artifact_data=artifact_data
        )

        # Assertions
        assert artifact.id is not None
        assert artifact.status == "scheduled"
        assert artifact.progress_percent == 0
        assert artifact.file_path is None  # ✅ Still NULL
        assert artifact.started_at == started_at
        assert artifact.completed_at is None
        assert artifact.error_message is None

    # ============================================================================
    # TC-DB-002: Update Artifact status during work (file_path=NULL)
    # ============================================================================
    def test_update_artifact_progress_null_file_path(self):
        """
        TC-DB-002: 작업 중 Artifact 상태 업데이트 시 file_path=NULL로 유지되어야 함.

        목적: 진행 중 progress를 업데이트하면서 file_path는 NULL로 유지됨을 검증.
        """
        # Create artifact with scheduled status
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            locale="ko",
            version=1,
            filename="report.md",
            file_path=None,
            file_size=0,
            status="scheduled",
            progress_percent=0,
            started_at=datetime.now().isoformat()
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        artifact_id = artifact.id

        # Step 1: Update to generating, progress=10%
        artifact = ArtifactDB.update_artifact_status(
            artifact_id=artifact_id,
            status="generating",
            progress_percent=10
            # file_path NOT provided → remains NULL
        )

        assert artifact.status == "generating"
        assert artifact.progress_percent == 10
        assert artifact.file_path is None  # ✅ Still NULL

        # Step 2: Update progress=50%
        artifact = ArtifactDB.update_artifact_status(
            artifact_id=artifact_id,
            status="generating",
            progress_percent=50
        )

        assert artifact.progress_percent == 50
        assert artifact.file_path is None  # ✅ Still NULL

    # ============================================================================
    # TC-DB-003: Add file information at completion
    # ============================================================================
    def test_add_file_info_at_completion(self):
        """
        TC-DB-003: 작업 완료 시 file_path, file_size, sha256가 추가되어야 함.

        목적: 작업이 완료될 때 file 정보를 NULL에서 populated로 변경할 수 있음을 검증.
        """
        # Create artifact with scheduled status
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            locale="ko",
            version=1,
            filename="report.md",
            file_path=None,  # NULL at creation
            file_size=0,
            status="scheduled",
            progress_percent=0,
            started_at=datetime.now().isoformat()
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        artifact_id = artifact.id

        # Simulate work completion: update status + add file info
        completed_at = datetime.now().isoformat()
        artifact = ArtifactDB.update_artifact_status(
            artifact_id=artifact_id,
            status="completed",
            progress_percent=100,
            file_path="artifacts/topics/1/messages/1/report.md",  # ✅ Add file path
            file_size=2048,  # ✅ Add file size
            sha256="abc123def456",  # ✅ Add hash
            completed_at=completed_at
        )

        # Assertions: file info should be populated
        assert artifact.status == "completed"
        assert artifact.progress_percent == 100
        assert artifact.file_path == "artifacts/topics/1/messages/1/report.md"  # ✅ Populated
        assert artifact.file_size == 2048
        assert artifact.sha256 == "abc123def456"
        assert artifact.completed_at == completed_at

    # ============================================================================
    # TC-DB-004: Mark artifact as failed without file_path
    # ============================================================================
    def test_mark_artifact_failed_without_file_path(self):
        """
        TC-DB-004: 작업 실패 시 error_message를 기록하면서 file_path는 NULL 유지.

        목적: 실패 상태에서도 file_path가 NULL로 유지됨을 검증.
        """
        # Create artifact
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            locale="ko",
            version=1,
            filename="report.md",
            file_path=None,
            file_size=0,
            status="scheduled",
            progress_percent=0,
            started_at=datetime.now().isoformat()
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        artifact_id = artifact.id

        # Simulate failure
        artifact = ArtifactDB.update_artifact_status(
            artifact_id=artifact_id,
            status="failed",
            progress_percent=50,  # Failed at 50% progress
            error_message="Claude API timeout after 30 seconds",
            completed_at=datetime.now().isoformat()
        )

        # Assertions
        assert artifact.status == "failed"
        assert artifact.progress_percent == 50
        assert artifact.file_path is None  # ✅ Still NULL
        assert artifact.error_message == "Claude API timeout after 30 seconds"

    # ============================================================================
    # TC-DB-005: Backward compatibility (existing artifacts with status=completed)
    # ============================================================================
    def test_backward_compatibility_existing_artifacts(self):
        """
        TC-DB-005: 기존 Artifact (v2.4 이하)와 호환성 유지.

        목적: 마이그레이션 후 기존 artifacts도 status="completed"로 작동하는지 검증.
        """
        # Create artifact with default backward-compatible values
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            locale="ko",
            version=1,
            filename="report.md",
            file_path="artifacts/topics/1/messages/1/report.md",  # Has file_path
            file_size=1024,
            sha256="xyz789"
            # status and progress_percent use defaults: "completed", 100
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)

        # Assertions: should use backward-compatible defaults
        assert artifact.status == "completed"
        assert artifact.progress_percent == 100
        assert artifact.file_path == "artifacts/topics/1/messages/1/report.md"
        assert artifact.file_size == 1024

    # ============================================================================
    # TC-DB-006: Retrieve artifact state at any point
    # ============================================================================
    def test_retrieve_artifact_at_any_state(self):
        """
        TC-DB-006: 어떤 상태에서든 Artifact 조회 가능 (scheduled, generating, completed, failed).

        목적: 중간 상태에서도 정확한 정보를 조회할 수 있음을 검증.
        """
        # Create artifact
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report.md",
            file_path=None,
            status="scheduled",
            progress_percent=0,
            started_at=datetime.now().isoformat()
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        artifact_id = artifact.id

        # Retrieve at scheduled state
        retrieved = ArtifactDB.get_artifact_by_id(artifact_id)
        assert retrieved.status == "scheduled"
        assert retrieved.progress_percent == 0

        # Update to generating
        ArtifactDB.update_artifact_status(
            artifact_id,
            status="generating",
            progress_percent=50
        )

        # Retrieve at generating state
        retrieved = ArtifactDB.get_artifact_by_id(artifact_id)
        assert retrieved.status == "generating"
        assert retrieved.progress_percent == 50

        # Update to completed
        ArtifactDB.update_artifact_status(
            artifact_id,
            status="completed",
            progress_percent=100,
            file_path="artifacts/report.md",
            file_size=1024,
            completed_at=datetime.now().isoformat()
        )

        # Retrieve at completed state
        retrieved = ArtifactDB.get_artifact_by_id(artifact_id)
        assert retrieved.status == "completed"
        assert retrieved.progress_percent == 100
        assert retrieved.file_path == "artifacts/report.md"

    # ============================================================================
    # TC-DB-007: Multiple artifacts with different states (independent)
    # ============================================================================
    def test_multiple_artifacts_different_states_independent(self):
        """
        TC-DB-007: 여러 artifact가 상태를 독립적으로 관리할 수 있음.

        목적: 같은 topic의 여러 artifact 상태가 서로 영향을 주지 않음을 검증.
        """
        # Create artifact 1 (scheduled)
        artifact_data1 = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report_v1.md",
            file_path=None,
            status="scheduled",
            progress_percent=0,
            started_at=datetime.now().isoformat()
        )
        artifact1 = ArtifactDB.create_artifact(1, 1, artifact_data1)

        # Create artifact 2 (generating)
        artifact_data2 = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report_v2.md",
            file_path=None,
            status="generating",
            progress_percent=50,
            started_at=datetime.now().isoformat()
        )
        artifact2 = ArtifactDB.create_artifact(2, 2, artifact_data2)

        # Create artifact 3 (completed)
        artifact_data3 = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report_v3.md",
            file_path="artifacts/report.md",
            file_size=2048,
            status="completed",
            progress_percent=100
        )
        artifact3 = ArtifactDB.create_artifact(3, 3, artifact_data3)

        # Verify independent states by direct ID lookup (no topic filtering)
        a1 = ArtifactDB.get_artifact_by_id(artifact1.id)
        a2 = ArtifactDB.get_artifact_by_id(artifact2.id)
        a3 = ArtifactDB.get_artifact_by_id(artifact3.id)

        assert a1.status == "scheduled"
        assert a2.status == "generating"
        assert a3.status == "completed"

        # Verify states are independent
        assert a1.progress_percent == 0
        assert a2.progress_percent == 50
        assert a3.progress_percent == 100

    # ============================================================================
    # Error Scenario 1: Invalid status value
    # ============================================================================
    def test_error_invalid_status_value(self):
        """
        Error-001: Invalid status 값은 제약이 없음 (현재, 추후 validation 추가 가능).

        목적: 잘못된 status 값이 저장될 수 있음을 인식.
        """
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report.md",
            file_path=None,
            status="invalid_status"  # Invalid, but allowed by DB
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        assert artifact.status == "invalid_status"

        # Validation should be added at router level to prevent this

    # ============================================================================
    # Error Scenario 2: Progress percent validation at model level
    # ============================================================================
    def test_error_progress_validation_at_model_level(self):
        """
        Error-002: Pydantic는 progress_percent 범위를 0-100으로 강제 (모델 level validation).

        목적: ArtifactCreate 모델에서 이미 범위 검증이 일어남을 확인.
        """
        # This should fail validation at Pydantic model level
        with pytest.raises(Exception):  # Pydantic ValidationError
            artifact_data = ArtifactCreate(
                kind=ArtifactKind.MD,
                filename="report.md",
                progress_percent=150  # Out of range
            )

    # ============================================================================
    # Error Scenario 3: File size with NULL file_path (inconsistent state)
    # ============================================================================
    def test_error_file_size_with_null_file_path(self):
        """
        Error-003: file_size > 0 이면서 file_path=NULL인 비정상 상태 저장 가능.

        목적: 상태 일관성 검사가 router level에서 필요함을 인식.
        """
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report.md",
            file_path=None,  # NULL
            file_size=2048  # But has size
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        assert artifact.file_path is None
        assert artifact.file_size == 2048  # Inconsistent state

        # Consistency check should be added at router level

    # ============================================================================
    # Error Scenario 4: Completed timestamp without completed status
    # ============================================================================
    def test_error_completed_timestamp_without_status(self):
        """
        Error-004: completed_at가 있지만 status != "completed"인 비정상 상태.

        목적: 상태 필드 간 일관성 검사가 필요함을 인식.
        """
        artifact_data = ArtifactCreate(
            kind=ArtifactKind.MD,
            filename="report.md",
            status="generating",  # Still generating
            completed_at=datetime.now().isoformat()  # But marked as completed
        )

        artifact = ArtifactDB.create_artifact(1, 1, artifact_data)
        assert artifact.status == "generating"
        assert artifact.completed_at is not None  # Inconsistent

        # State consistency check should be added at router level


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
