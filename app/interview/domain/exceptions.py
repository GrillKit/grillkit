# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview domain exceptions."""


class InterviewDomainError(Exception):
    """Base class for interview-related domain errors."""


class InterviewNotFoundError(InterviewDomainError):
    """Raised when an interview ID does not exist."""

    def __init__(self, interview_id: str) -> None:
        """Initialize with the missing interview ID.

        Args:
            interview_id: Requested interview UUID.
        """
        self.interview_id = interview_id
        super().__init__(f"Interview not found: {interview_id}")


class InterviewNotActiveError(InterviewDomainError):
    """Raised when an operation requires an active interview."""

    def __init__(self, interview_id: str | None = None) -> None:
        """Initialize optionally with the interview ID.

        Args:
            interview_id: Interview UUID, if known.
        """
        self.interview_id = interview_id
        super().__init__("Cannot submit answer to a completed interview")
