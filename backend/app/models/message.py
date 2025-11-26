"""
Message models for chat-based conversation.

Messages represent individual turns in a conversation (user/assistant).
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from shared.types.enums import MessageRole


class MessageCreate(BaseModel):
    """Request model for creating a new message.

    Attributes:
        role: Message role (user/assistant/system)
        content: Message content text
    """
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., min_length=1, max_length=50000, description="Message content")


class Message(BaseModel):
    """Full message entity model.

    Attributes:
        id: Message ID
        topic_id: ID of the parent topic
        role: Message role (user/assistant/system)
        content: Message text content
        seq_no: Sequential number within the topic (for ordering)
        created_at: Creation timestamp
    """
    id: int
    topic_id: int
    role: MessageRole
    content: str
    seq_no: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Public message response model.

    Suitable for API responses.

    Attributes:
        id: Message ID
        topic_id: Parent topic ID
        role: Message role
        content: Message content
        seq_no: Sequential order
        created_at: Creation timestamp
    """
    id: int
    topic_id: int
    role: MessageRole
    content: str
    seq_no: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Paginated list of messages.

    Attributes:
        messages: List of message responses
        total: Total number of messages in the topic
        topic_id: Parent topic ID
    """
    messages: list[MessageResponse]
    total: int
    topic_id: int


class AskRequest(BaseModel):
    """Request model for asking question in conversation.

    Attributes:
        content: User question (1-50,000 chars)
        artifact_id: Specific artifact to reference (null = use latest MD)
        include_artifact_content: Include file content in context (default: false)
        max_messages: Max number of user messages to include (null = all)
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="User question text"
    )

    artifact_id: Optional[int] = Field(
        default=None,
        description="Artifact ID to reference (null = use latest MD)"
    )

    include_artifact_content: bool = Field(
        default=False,
        description="Include artifact file content in context"
    )

    max_messages: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of user messages to include"
    )

    is_web_search: bool = Field(
        default=False,
        alias="isWebSearch",
        description="Enable Claude web search tool (default: false)"
    )

    class Config:
        populate_by_name = True
