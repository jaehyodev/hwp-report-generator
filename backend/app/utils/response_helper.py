"""
API response helper functions.

Provides standardized success and error response generation for all API endpoints.
"""
import uuid
from typing import Any, List, Dict, Optional
from fastapi.responses import JSONResponse
from shared.models.api_response import ApiResponse, ErrorResponse, Feedback, FeedbackLevel


def success_response(
    data: Any,
    feedback: Optional[List[Feedback]] = None
) -> Dict[str, Any]:
    """Generates a standardized success response.

    Args:
        data: Response data (any JSON-serializable type)
        feedback: Optional list of user feedback messages

    Returns:
        Dictionary matching ApiResponse structure

    Examples:
        >>> response = success_response({"report_id": 123, "filename": "report.hwpx"})
        >>> print(response["success"])
        True
    """
    return {
        "success": True,
        "data": data,
        "error": None,
        "meta": {"requestId": str(uuid.uuid4())},
        "feedback": feedback or []
    }


def error_response(
    code: str,
    http_status: int,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    hint: Optional[str] = None
) -> JSONResponse:
    """Generates a standardized error response with proper HTTP status.

    Args:
        code: Error code in DOMAIN.DETAIL format (e.g., "AUTH.INVALID_TOKEN")
        http_status: HTTP status code (401, 404, 500, etc.)
        message: User-friendly error message
        details: Additional error details (optional)
        hint: Suggested action for user (optional)

    Returns:
        FastAPI JSONResponse with error structure

    Examples:
        >>> response = error_response(
        ...     code="TOPIC.NOT_FOUND",
        ...     http_status=404,
        ...     message="Topic not found",
        ...     hint="Please check the topic ID"
        ... )
        >>> print(response.status_code)
        404
    """
    return JSONResponse(
        status_code=http_status,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "httpStatus": http_status,
                "message": message,
                "details": details,
                "traceId": str(uuid.uuid4()),
                "hint": hint
            },
            "meta": {"requestId": str(uuid.uuid4())},
            "feedback": []
        }
    )


def success_response_with_feedback(
    data: Any,
    feedback_code: str,
    feedback_level: FeedbackLevel,
    feedback_message: str
) -> Dict[str, Any]:
    """Generates a success response with a single feedback message.

    Args:
        data: Response data
        feedback_code: Feedback identifier code
        feedback_level: Feedback level (info/warning/error)
        feedback_message: Feedback message

    Returns:
        Dictionary matching ApiResponse structure with feedback

    Examples:
        >>> response = success_response_with_feedback(
        ...     data={"template_id": 45},
        ...     feedback_code="TEMPLATE.MISSING_PLACEHOLDERS",
        ...     feedback_level=FeedbackLevel.WARNING,
        ...     feedback_message="SUMMARY placeholder is missing"
        ... )
        >>> print(response["feedback"][0]["level"])
        warning
    """
    feedback = [Feedback(
        code=feedback_code,
        level=feedback_level,
        feedbackCd=feedback_message
    )]

    return success_response(data, feedback)


# Common error code constants
class ErrorCode:
    """Standard error codes for the application.

    Error codes follow the format: DOMAIN.DETAIL
    """

    # Authentication errors (AUTH.*)
    AUTH_INVALID_TOKEN = "AUTH.INVALID_TOKEN"
    AUTH_TOKEN_EXPIRED = "AUTH.TOKEN_EXPIRED"
    AUTH_UNAUTHORIZED = "AUTH.UNAUTHORIZED"
    AUTH_INVALID_CREDENTIALS = "AUTH.INVALID_CREDENTIALS"
    AUTH_DUPLICATE_EMAIL = "AUTH.DUPLICATE_EMAIL"
    AUTH_ACCOUNT_INACTIVE = "AUTH.ACCOUNT_INACTIVE"
    AUTH_INVALID_PASSWORD = "AUTH.INVALID_PASSWORD"

    # Admin errors (ADMIN.*)
    ADMIN_USER_NOT_FOUND = "ADMIN.USER_NOT_FOUND"

    # Topic errors (TOPIC.*)
    TOPIC_NOT_FOUND = "TOPIC.NOT_FOUND"
    TOPIC_CREATION_FAILED = "TOPIC.CREATION_FAILED"
    TOPIC_UNAUTHORIZED = "TOPIC.UNAUTHORIZED"

    # Message errors (MESSAGE.*)
    MESSAGE_NOT_FOUND = "MESSAGE.NOT_FOUND"
    MESSAGE_CREATION_FAILED = "MESSAGE.CREATION_FAILED"
    MESSAGE_INVALID_ROLE = "MESSAGE.INVALID_ROLE"
    MESSAGE_CONTEXT_TOO_LARGE = "MESSAGE.CONTEXT_TOO_LARGE"

    # Artifact errors (ARTIFACT.*)
    ARTIFACT_NOT_FOUND = "ARTIFACT.NOT_FOUND"
    ARTIFACT_CREATION_FAILED = "ARTIFACT.CREATION_FAILED"
    ARTIFACT_DOWNLOAD_FAILED = "ARTIFACT.DOWNLOAD_FAILED"
    ARTIFACT_INVALID_KIND = "ARTIFACT.INVALID_KIND"
    ARTIFACT_CONVERSION_FAILED = "ARTIFACT.CONVERSION_FAILED"
    ARTIFACT_UNAUTHORIZED = "ARTIFACT.UNAUTHORIZED"

    # Template errors (TEMPLATE.*)
    TEMPLATE_NOT_FOUND = "TEMPLATE.NOT_FOUND"
    TEMPLATE_INVALID_FORMAT = "TEMPLATE.INVALID_FORMAT"
    TEMPLATE_DUPLICATE_PLACEHOLDER = "TEMPLATE.DUPLICATE_PLACEHOLDER"
    TEMPLATE_UNAUTHORIZED = "TEMPLATE.UNAUTHORIZED"
    TEMPLATE_FORBIDDEN = "TEMPLATE.FORBIDDEN"
    TEMPLATE_INVALID_PROMPT = "TEMPLATE.INVALID_PROMPT"
    TEMPLATE_GENERATION_FAILED = "TEMPLATE.GENERATION_FAILED"

    # Prompt optimization errors (PROMPT_OPTIMIZATION.*)
    PROMPT_OPTIMIZATION_TIMEOUT = "PROMPT_OPTIMIZATION.TIMEOUT"
    PROMPT_OPTIMIZATION_ERROR = "PROMPT_OPTIMIZATION.ERROR"

    # Report errors (REPORT.*)
    REPORT_GENERATION_FAILED = "REPORT.GENERATION_FAILED"
    REPORT_NOT_FOUND = "REPORT.NOT_FOUND"
    REPORT_UNAUTHORIZED = "REPORT.UNAUTHORIZED"
    REPORT_FILE_NOT_FOUND = "REPORT.FILE_NOT_FOUND"

    # Validation errors (VALIDATION.*)
    VALIDATION_REQUIRED_FIELD = "VALIDATION.REQUIRED_FIELD"
    VALIDATION_INVALID_FORMAT = "VALIDATION.INVALID_FORMAT"
    VALIDATION_MAX_LENGTH_EXCEEDED = "VALIDATION.MAX_LENGTH_EXCEEDED"
    VALIDATION_ERROR = "VALIDATION.ERROR"

    # Request errors (REQUEST.*)
    REQUEST_TIMEOUT = "REQUEST.TIMEOUT"
    CONFLICT = "REQUEST.CONFLICT"
    NOT_FOUND = "RESOURCE.NOT_FOUND"

    # Server errors (SERVER.*)
    SERVER_INTERNAL_ERROR = "SERVER.INTERNAL_ERROR"
    SERVER_SERVICE_UNAVAILABLE = "SERVER.SERVICE_UNAVAILABLE"
    SERVER_DATABASE_ERROR = "SERVER.DATABASE_ERROR"
