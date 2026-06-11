# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory domain exceptions."""


class TheoryDomainError(Exception):
    """Base class for theory-related domain errors."""


class TheorySectionNotFoundError(TheoryDomainError):
    """Raised when a theory section does not exist for an interview."""

    def __init__(self, interview_id: str) -> None:
        """Initialize with the parent interview ID.

        Args:
            interview_id: Parent interview UUID.
        """
        self.interview_id = interview_id
        super().__init__(f"Theory section not found for interview: {interview_id}")


class TheorySectionNotActiveError(TheoryDomainError):
    """Raised when an operation requires an active theory section."""

    def __init__(self, interview_id: str | None = None) -> None:
        """Initialize optionally with the interview ID.

        Args:
            interview_id: Parent interview UUID, if known.
        """
        self.interview_id = interview_id
        super().__init__("Cannot submit answer to a completed theory section")


class UnansweredTaskNotFoundError(TheoryDomainError):
    """Raised when no open task row exists for a question."""

    def __init__(self, interview_id: str, question_id: str) -> None:
        """Initialize with interview and question identifiers.

        Args:
            interview_id: Parent interview UUID.
            question_id: YAML question ID.
        """
        self.interview_id = interview_id
        self.question_id = question_id
        super().__init__(
            f"Unanswered theory task not found: interview={interview_id}, "
            f"question={question_id}"
        )


class TaskTimerNotEnabledError(TheoryDomainError):
    """Raised when a timer operation is requested but the section has no limit."""

    def __init__(self, interview_id: str) -> None:
        """Initialize with the interview ID.

        Args:
            interview_id: Parent interview UUID.
        """
        self.interview_id = interview_id
        super().__init__(
            f"Task timer is not enabled for theory section: {interview_id}"
        )


class TaskTimerNotExpiredError(TheoryDomainError):
    """Raised when a timeout is submitted before the task deadline."""

    def __init__(self, interview_id: str, question_id: str) -> None:
        """Initialize with interview and question identifiers.

        Args:
            interview_id: Parent interview UUID.
            question_id: YAML question ID.
        """
        self.interview_id = interview_id
        self.question_id = question_id
        super().__init__(
            f"Task timer has not expired: interview={interview_id}, "
            f"question={question_id}"
        )


class TheoryTaskNotFoundError(TheoryDomainError):
    """Raised when a specific theory task row is missing."""

    def __init__(self, interview_id: str, question_id: str, round_num: int) -> None:
        """Initialize with lookup keys.

        Args:
            interview_id: Parent interview UUID.
            question_id: YAML question ID.
            round_num: Task round (0 = initial).
        """
        self.interview_id = interview_id
        self.question_id = question_id
        self.round_num = round_num
        super().__init__(
            f"Theory task not found: interview={interview_id}, "
            f"question={question_id}, round={round_num}"
        )
