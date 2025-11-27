"""
Shared enums for the hwp-report-generator project.

These enums are used by both backend (Python) and frontend (TypeScript).
"""
from enum import Enum


class MessageRole(str, Enum):
    """Role of a message in a conversation.

    Attributes:
        USER: Message from the user
        ASSISTANT: Response from the AI assistant
        SYSTEM: System-generated message (e.g., migration placeholder)
    """
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ArtifactKind(str, Enum):
    """Type of artifact file.

    Attributes:
        MD: Markdown file (.md)
        HWPX: Hangul Word Processor file (.hwpx)
        PDF: PDF document (.pdf) - reserved for future use
    """
    MD = "md"
    HWPX = "hwpx"
    PDF = "pdf"


class TopicStatus(str, Enum):
    """Status of a topic/conversation.

    Attributes:
        ACTIVE: Topic is actively being worked on
        ARCHIVED: Topic is archived but can be reopened
        DELETED: Topic is marked for deletion (soft delete)
    """
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class TransformOperation(str, Enum):
    """Type of transformation operation between artifacts.

    Attributes:
        CONVERT: Format conversion (e.g., MD → HWPX)
        TRANSLATE: Language translation (e.g., KO → EN)
    """
    CONVERT = "convert"
    TRANSLATE = "translate"


class TopicSourceType(str, Enum):
    """Source type of a topic/conversation.

    Determines how the topic is processed and which prompts are used:
    - TEMPLATE: Template-based workflow (requires template_id)
    - BASIC: Basic/optimization-based workflow (uses prompt optimization or default prompts)

    Attributes:
        TEMPLATE: Template-based report generation
        BASIC: Basic/optimization-based report generation
    """
    TEMPLATE = "template"
    BASIC = "basic"
