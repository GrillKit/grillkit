# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Map coding domain errors to HTTP and WebSocket responses."""

from fastapi import HTTPException

from app.coding.domain.exceptions import (
    CodingDomainError,
    CodingRunLimitExceededError,
    CodingSectionNotActiveError,
    CodingSectionNotFoundError,
    CodingTaskNotCurrentError,
    CodingTaskNotFoundError,
)
from app.interview.domain.exceptions import (
    InterviewDomainError,
    InterviewNotActiveError,
    InterviewNotFoundError,
)


def coding_ws_error_payload(
    exc: CodingDomainError | InterviewDomainError,
) -> dict[str, str]:
    """Build a WebSocket error payload from a domain exception.

    Args:
        exc: Domain error raised by the service layer.

    Returns:
        JSON-serializable error dict for the client.
    """
    return {"type": "error", "message": str(exc)}


def http_exception_from_coding_error(
    exc: CodingDomainError | InterviewDomainError,
) -> HTTPException:
    """Convert a domain exception to an HTTPException.

    Args:
        exc: Domain error raised by the service layer.

    Returns:
        HTTPException with an appropriate status code.
    """
    if isinstance(
        exc,
        InterviewNotFoundError | CodingSectionNotFoundError | CodingTaskNotFoundError,
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CodingRunLimitExceededError):
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(
        exc,
        InterviewNotActiveError
        | CodingSectionNotActiveError
        | CodingTaskNotCurrentError,
    ):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
