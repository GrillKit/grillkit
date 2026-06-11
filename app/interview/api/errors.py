# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Map interview domain errors to HTTP and WebSocket responses."""

from fastapi import HTTPException

from app.interview.domain.exceptions import (
    AnswerNotFoundError,
    InterviewDomainError,
    InterviewNotActiveError,
    InterviewNotFoundError,
    QuestionTimerNotEnabledError,
    QuestionTimerNotExpiredError,
    UnansweredAnswerNotFoundError,
)
from app.theory.api.ws_protocol import domain_error_to_wire
from app.theory.domain.exceptions import (
    TaskTimerNotEnabledError,
    TaskTimerNotExpiredError,
    TheoryDomainError,
    TheorySectionNotActiveError,
    TheorySectionNotFoundError,
    TheoryTaskNotFoundError,
    UnansweredTaskNotFoundError,
)


def ws_error_payload(exc: InterviewDomainError | TheoryDomainError) -> dict[str, str]:
    """Build a WebSocket error message from a domain exception.

    Args:
        exc: Domain error raised by the service layer.

    Returns:
        JSON-serializable error dict for the client.
    """
    return domain_error_to_wire(exc)


def http_exception_from_domain_error(
    exc: InterviewDomainError | TheoryDomainError,
) -> HTTPException:
    """Convert a domain exception to an HTTPException.

    Args:
        exc: Domain error raised by the service layer.

    Returns:
        HTTPException with an appropriate status code.
    """
    if isinstance(
        exc,
        InterviewNotFoundError
        | AnswerNotFoundError
        | TheorySectionNotFoundError
        | TheoryTaskNotFoundError,
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(
        exc,
        InterviewNotActiveError
        | UnansweredAnswerNotFoundError
        | QuestionTimerNotEnabledError
        | QuestionTimerNotExpiredError
        | TheorySectionNotActiveError
        | UnansweredTaskNotFoundError
        | TaskTimerNotEnabledError
        | TaskTimerNotExpiredError,
    ):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
