"""
Artifact models for generated files (MD, HWPX, PDF).

Artifacts represent generated files at various stages of the report creation process.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from shared.types.enums import ArtifactKind


class ArtifactCreate(BaseModel):
    """Request model for creating a new artifact.

    Attributes:
        kind: Artifact type (md/hwpx/pdf)
        locale: Language/locale code (ko/en)
        version: Version number (default: 1)
        filename: File name
        file_path: File storage path (optional, can be NULL during work)
        file_size: File size in bytes
        sha256: SHA256 hash for deduplication (optional)
        status: Generation status (scheduled/generating/completed/failed, default: completed for backward compatibility)
        progress_percent: Progress percentage (0-100, default: 100 for backward compatibility)
        started_at: Work start timestamp (ISO 8601)
        completed_at: Work completion timestamp (ISO 8601, optional)
        error_message: Error message if status=failed (optional)
    """
    kind: ArtifactKind = Field(..., description="Artifact type")
    locale: str = Field(default="ko", max_length=10, description="Language code")
    version: int = Field(default=1, ge=1, description="Version number")
    filename: str = Field(..., max_length=255, description="File name")
    file_path: Optional[str] = Field(None, max_length=500, description="File storage path (NULL during work)")
    file_size: int = Field(default=0, ge=0, description="File size in bytes")
    sha256: Optional[str] = Field(None, max_length=64, description="SHA256 hash")

    # State management fields (v2.5+, Option A)
    status: str = Field(default="completed", description="Generation status: scheduled/generating/completed/failed")
    progress_percent: int = Field(default=100, ge=0, le=100, description="Progress percentage (0-100)")
    started_at: Optional[str] = Field(None, description="Work start timestamp (ISO 8601)")
    completed_at: Optional[str] = Field(None, description="Work completion timestamp (ISO 8601)")
    error_message: Optional[str] = Field(None, max_length=500, description="Error message if failed")


class Artifact(BaseModel):
    """Full artifact entity model.

    Attributes:
        id: Artifact ID
        topic_id: ID of the parent topic
        message_id: ID of the message that generated this artifact (optional for background generation)
        kind: Artifact type
        locale: Language code
        version: Version number
        filename: File name
        file_path: File storage path (can be NULL during work)
        file_size: File size in bytes
        sha256: SHA256 hash (optional)
        created_at: Creation timestamp
        status: Generation status (scheduled/generating/completed/failed)
        progress_percent: Progress percentage (0-100)
        started_at: Work start timestamp
        completed_at: Work completion timestamp
        error_message: Error message if failed
    """
    id: int
    topic_id: int
    message_id: Optional[int] = None
    kind: ArtifactKind
    locale: str
    version: int
    filename: str
    file_path: Optional[str] = None
    file_size: int
    sha256: Optional[str] = None
    created_at: datetime

    # State management fields (v2.5+, Option A)
    status: str = "completed"
    progress_percent: int = 100
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ArtifactResponse(BaseModel):
    """Public artifact response model.

    Suitable for API responses.

    Attributes:
        id: Artifact ID
        topic_id: Parent topic ID
        message_id: Source message ID (optional for background generation)
        kind: Artifact type
        locale: Language code
        version: Version number
        filename: File name
        file_path: File storage path (may be relative, NULL during work)
        file_size: File size in bytes
        created_at: Creation timestamp
        status: Generation status
        progress_percent: Progress percentage
        started_at: Work start timestamp
        completed_at: Work completion timestamp
        error_message: Error message if failed
    """
    id: int
    topic_id: int
    message_id: Optional[int] = None
    kind: ArtifactKind
    locale: str
    version: int
    filename: str
    file_path: Optional[str] = None
    file_size: int
    created_at: datetime

    # State management fields (v2.5+, Option A)
    status: str = "completed"
    progress_percent: int = 100
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ArtifactListResponse(BaseModel):
    """Paginated list of artifacts.

    Attributes:
        artifacts: List of artifact responses
        total: Total number of artifacts
        topic_id: Parent topic ID (optional filter)
    """
    artifacts: list[ArtifactResponse]
    total: int
    topic_id: Optional[int] = None


class ArtifactContentResponse(BaseModel):
    """Response model for artifact content (e.g., MD file).

    Attributes:
        artifact_id: Artifact ID
        content: File content as text
        filename: File name
        kind: Artifact type
    """
    artifact_id: int
    content: str
    filename: str
    kind: ArtifactKind
