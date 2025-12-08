"""
Artifact database operations.

Handles CRUD operations for artifacts (generated files: MD, HWPX, PDF).
"""
from typing import Optional, List, Tuple
from datetime import datetime
from .connection import get_db_connection
from app.models.artifact import Artifact, ArtifactCreate
from shared.types.enums import ArtifactKind


class ArtifactDB:
    """Artifact database class for CRUD operations."""

    @staticmethod
    def create_artifact(
        topic_id: int,
        message_id: Optional[int],
        artifact_data: ArtifactCreate
    ) -> Artifact:
        """Creates a new artifact.

        Supports immediate creation with state tracking (v2.5+ Option A):
        - Artifact can be created with status="scheduled" and file_path=NULL
        - State updates (progress, file info) happen via update_artifact_status()
        - Backward compatible: defaults to status="completed" if not specified
        - message_id can be NULL for background generation (message created later)

        Args:
            topic_id: Parent topic ID
            message_id: Source message ID (optional for background generation)
            artifact_data: Artifact creation data (can have status and NULL file_path)

        Returns:
            Created artifact entity

        Examples:
            >>> # Immediate creation (status="scheduled", file_path=NULL)
            >>> artifact_data = ArtifactCreate(
            ...     kind=ArtifactKind.MD,
            ...     filename="report.md",
            ...     file_path=None,  # NULL during work
            ...     status="scheduled",
            ...     started_at="2025-11-15T10:00:00"
            ... )
            >>> artifact = ArtifactDB.create_artifact(1, None, artifact_data)

            >>> # With message_id
            >>> artifact = ArtifactDB.create_artifact(1, 2, artifact_data)

            >>> # Backward compatible (status="completed")
            >>> artifact_data = ArtifactCreate(
            ...     kind=ArtifactKind.MD,
            ...     filename="report.md",
            ...     file_path="artifacts/topics/1/messages/report.md",
            ...     file_size=1024
            ... )
            >>> artifact = ArtifactDB.create_artifact(1, 2, artifact_data)
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        cursor.execute(
            """
            INSERT INTO artifacts (
                topic_id, message_id, kind, locale, version,
                filename, file_path, file_size, sha256, created_at,
                status, progress_percent, started_at, completed_at, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic_id,
                message_id,
                artifact_data.kind.value,
                artifact_data.locale,
                artifact_data.version,
                artifact_data.filename,
                artifact_data.file_path,
                artifact_data.file_size,
                artifact_data.sha256,
                now,
                artifact_data.status,
                artifact_data.progress_percent,
                artifact_data.started_at,
                artifact_data.completed_at,
                artifact_data.error_message
            )
        )

        conn.commit()
        artifact_id = cursor.lastrowid

        # Retrieve created artifact
        cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
        row = cursor.fetchone()
        conn.close()

        return ArtifactDB._row_to_artifact(row)

    @staticmethod
    def get_artifact_by_id(artifact_id: int) -> Optional[Artifact]:
        """Retrieves artifact by ID.

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact entity or None if not found
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
        row = cursor.fetchone()
        conn.close()

        return ArtifactDB._row_to_artifact(row) if row else None

    @staticmethod
    def get_artifacts_by_topic(
        topic_id: int,
        kind: Optional[ArtifactKind] = None,
        locale: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Artifact], int]:
        """Retrieves artifacts for a topic with optional filters.

        Args:
            topic_id: Topic ID
            kind: Filter by artifact kind (optional)
            locale: Filter by locale (optional)
            limit: Maximum number of artifacts to return
            offset: Number of artifacts to skip

        Returns:
            Tuple of (list of artifacts, total count)

        Examples:
            >>> artifacts, total = ArtifactDB.get_artifacts_by_topic(1, kind=ArtifactKind.MD)
            >>> print(f"Found {total} MD files")
            Found 3 MD files
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with optional filters
        query = "SELECT * FROM artifacts WHERE topic_id = ?"
        count_query = "SELECT COUNT(*) FROM artifacts WHERE topic_id = ?"
        params = [topic_id]

        if kind:
            query += " AND kind = ?"
            count_query += " AND kind = ?"
            params.append(kind.value)

        if locale:
            query += " AND locale = ?"
            count_query += " AND locale = ?"
            params.append(locale)

        # Get total count
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get artifacts ordered by created_at DESC
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        artifacts = [ArtifactDB._row_to_artifact(row) for row in rows]
        return artifacts, total

    @staticmethod
    def get_artifacts_by_message(message_id: int) -> List[Artifact]:
        """Retrieves all artifacts generated by a specific message.

        Args:
            message_id: Message ID

        Returns:
            List of artifacts
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM artifacts WHERE message_id = ? ORDER BY created_at DESC",
            (message_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [ArtifactDB._row_to_artifact(row) for row in rows]

    @staticmethod
    def get_latest_artifact_by_kind(
        topic_id: int,
        kind: ArtifactKind,
        locale: str = "ko"
    ) -> Optional[Artifact]:
        """Retrieves the latest artifact of a specific kind and locale.

        Args:
            topic_id: Topic ID
            kind: Artifact kind
            locale: Locale code

        Returns:
            Latest artifact or None if not found

        Examples:
            >>> latest_md = ArtifactDB.get_latest_artifact_by_kind(1, ArtifactKind.MD, "ko")
            >>> if latest_md:
            ...     print(f"Latest version: {latest_md.version}")
            Latest version: 3
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM artifacts
            WHERE topic_id = ? AND kind = ? AND locale = ?
            ORDER BY version DESC, created_at DESC
            LIMIT 1
            """,
            (topic_id, kind.value, locale)
        )
        row = cursor.fetchone()
        conn.close()

        return ArtifactDB._row_to_artifact(row) if row else None

    @staticmethod
    def get_latest_artifact_by_message_and_kind(
        message_id: int,
        kind: ArtifactKind,
        locale: str = "ko"
    ) -> Optional[Artifact]:
        """Retrieves the latest artifact for a message filtered by kind and locale.

        Args:
            message_id: Source message ID
            kind: Artifact kind to filter (md/hwpx/pdf)
            locale: Locale code (default: "ko")

        Returns:
            Latest matching artifact or None if not found
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM artifacts
            WHERE message_id = ? AND kind = ? AND locale = ?
            ORDER BY version DESC, created_at DESC
            LIMIT 1
            """,
            (message_id, kind.value, locale)
        )
        row = cursor.fetchone()
        conn.close()

        return ArtifactDB._row_to_artifact(row) if row else None

    @staticmethod
    def delete_artifact(artifact_id: int) -> bool:
        """Deletes an artifact (hard delete, cascades to transformations).

        Args:
            artifact_id: Artifact ID

        Returns:
            True if deleted, False if not found
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        conn.commit()

        deleted = cursor.rowcount > 0
        conn.close()

        return deleted

    @staticmethod
    def update_artifact_status(
        artifact_id: int,
        status: str,
        message_id: Optional[int] = None,
        progress_percent: Optional[int] = None,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        sha256: Optional[str] = None,
        completed_at: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Artifact:
        """Updates artifact status and progress (v2.5+ Option A).

        Supports progressive state updates during work:
        - During work: status="generating", progress_percent (0-99), file_path=NULL
        - On completion: status="completed", progress_percent=100, file_path/file_size/sha256 added
        - On failure: status="failed", error_message added

        Note: file_path, file_size, sha256 remain NULL during work and are added only at completion.

        Args:
            artifact_id: Artifact ID to update
            status: New status (scheduled/generating/completed/failed)
            message_id: Source message to associate (optional)
            progress_percent: Progress percentage (0-100, optional)
            file_path: File path to add (optional, typically at completion)
            file_size: File size to add (optional, typically at completion)
            sha256: File hash to add (optional, typically at completion)
            completed_at: Completion timestamp (ISO 8601, optional)
            error_message: Error message (optional, for failed status)

        Returns:
            Updated artifact entity

        Examples:
            >>> # Update progress during work (file_path=NULL)
            >>> artifact = ArtifactDB.update_artifact_status(
            ...     artifact_id=1,
            ...     status="generating",
            ...     progress_percent=50
            ... )
            >>> print(artifact.file_path)  # Still NULL
            None

            >>> # Add file info at completion
            >>> artifact = ArtifactDB.update_artifact_status(
            ...     artifact_id=1,
            ...     status="completed",
            ...     progress_percent=100,
            ...     file_path="artifacts/topics/1/messages/report.md",
            ...     file_size=2048,
            ...     sha256="abc123...",
            ...     completed_at="2025-11-15T10:30:00"
            ... )
            >>> print(artifact.file_path)  # Now populated
            artifacts/topics/1/messages/report.md
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        updates = {"status": status}
        params = [status]

        if message_id is not None:
            updates["message_id"] = message_id
            params.append(message_id)

        if progress_percent is not None:
            updates["progress_percent"] = progress_percent
            params.append(progress_percent)

        if file_path is not None:
            updates["file_path"] = file_path
            params.append(file_path)

        if file_size is not None:
            updates["file_size"] = file_size
            params.append(file_size)

        if sha256 is not None:
            updates["sha256"] = sha256
            params.append(sha256)

        if completed_at is not None:
            updates["completed_at"] = completed_at
            params.append(completed_at)

        if error_message is not None:
            updates["error_message"] = error_message
            params.append(error_message)

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params.append(artifact_id)

        cursor.execute(
            f"""
            UPDATE artifacts
            SET {set_clause}
            WHERE id = ?
            """,
            params
        )

        conn.commit()

        # Retrieve updated artifact
        cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
        row = cursor.fetchone()
        conn.close()

        return ArtifactDB._row_to_artifact(row)

    @staticmethod
    def mark_failed(artifact_id: int, error_message: str) -> Artifact:
        """Marks an artifact as failed with error message (Task callback helper).

        This method is used by Task callbacks to quickly mark artifacts as failed
        without blocking the event loop. It performs a minimal DB update.

        Args:
            artifact_id: Artifact ID to mark as failed
            error_message: Error message (max 500 chars)

        Returns:
            Updated artifact entity

        Examples:
            >>> artifact = ArtifactDB.mark_failed(1, "Connection timeout")
        """
        return ArtifactDB.update_artifact_status(
            artifact_id=artifact_id,
            status="failed",
            error_message=error_message,
            completed_at=datetime.now().isoformat()
        )

    @staticmethod
    def _row_to_artifact(row) -> Artifact:
        """Converts database row to Artifact model.

        Handles state tracking fields (v2.5+ Option A):
        - status, progress_percent, started_at, completed_at, error_message

        Args:
            row: SQLite row object (dict-like)

        Returns:
            Artifact entity
        """
        # Helper function to safely get row values (handle missing columns for backward compatibility)
        def get_field(row, key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return Artifact(
            id=row["id"],
            topic_id=row["topic_id"],
            message_id=row["message_id"],
            kind=ArtifactKind(row["kind"]),
            locale=row["locale"],
            version=row["version"],
            filename=row["filename"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            sha256=row["sha256"],
            created_at=datetime.fromisoformat(row["created_at"]),

            # State management fields (v2.5+, Option A)
            status=get_field(row, "status", "completed"),
            progress_percent=get_field(row, "progress_percent", 100),
            started_at=get_field(row, "started_at"),
            completed_at=get_field(row, "completed_at"),
            error_message=get_field(row, "error_message")
        )
