# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Map interview domain errors to HTTP and WebSocket responses."""

from fastapi import HTTPException

from app.domain.exceptions import (
    AnswerNotFoundError,
    InterviewDomainError,
    InterviewNotActiveError,
    InterviewNotFoundError,
    UnansweredAnswerNotFoundError,
)


def ws_error_payload(exc: InterviewDomainError) -> dict[str, str]:
    """Build a WebSocket error message from a domain exception.

    Args:
        exc: Domain error raised by the service layer.

    Returns:
        JSON-serializable error dict for the client.
    """
    return {"type": "error", "message": str(exc)}


def http_exception_from_domain_error(exc: InterviewDomainError) -> HTTPException:
    """Convert a domain exception to an HTTPException.

    Args:
        exc: Domain error raised by the service layer.

    Returns:
        HTTPException with an appropriate status code.
    """
    if isinstance(exc, InterviewNotFoundError | AnswerNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, InterviewNotActiveError | UnansweredAnswerNotFoundError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
