# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Map interview domain errors to HTTP and WebSocket responses."""

from fastapi import HTTPException

from app.interview.domain.exceptions import (
    InterviewDomainError,
    InterviewNotActiveError,
    InterviewNotFoundError,
)
from app.theory.domain.exceptions import (
    TaskTimerNotEnabledError,
    TaskTimerNotExpiredError,
    TheoryDomainError,
    TheorySectionNotActiveError,
    TheorySectionNotFoundError,
    TheoryTaskNotFoundError,
    UnansweredTaskNotFoundError,
)


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
        InterviewNotFoundError | TheorySectionNotFoundError | TheoryTaskNotFoundError,
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(
        exc,
        InterviewNotActiveError
        | UnansweredTaskNotFoundError
        | TaskTimerNotEnabledError
        | TaskTimerNotExpiredError
        | TheorySectionNotActiveError,
    ):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))
