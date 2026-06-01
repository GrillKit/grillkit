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


class UnansweredAnswerNotFoundError(InterviewDomainError):
    """Raised when no open answer row exists for a question."""

    def __init__(self, interview_id: str, question_id: str) -> None:
        """Initialize with interview and question identifiers.

        Args:
            interview_id: Parent interview UUID.
            question_id: YAML question ID.
        """
        self.interview_id = interview_id
        self.question_id = question_id
        super().__init__(
            f"Unanswered answer not found: interview={interview_id}, "
            f"question={question_id}"
        )


class QuestionTimerNotEnabledError(InterviewDomainError):
    """Raised when a timer operation is requested but the session has no limit."""

    def __init__(self, interview_id: str) -> None:
        """Initialize with the interview ID.

        Args:
            interview_id: Interview UUID.
        """
        self.interview_id = interview_id
        super().__init__(f"Question timer is not enabled for interview: {interview_id}")


class QuestionTimerNotExpiredError(InterviewDomainError):
    """Raised when a timeout is submitted before the round deadline."""

    def __init__(self, interview_id: str, question_id: str) -> None:
        """Initialize with interview and question identifiers.

        Args:
            interview_id: Parent interview UUID.
            question_id: YAML question ID.
        """
        self.interview_id = interview_id
        self.question_id = question_id
        super().__init__(
            f"Question timer has not expired: interview={interview_id}, "
            f"question={question_id}"
        )


class AnswerNotFoundError(InterviewDomainError):
    """Raised when a specific answer row is missing."""

    def __init__(self, interview_id: str, question_id: str, round_num: int) -> None:
        """Initialize with lookup keys.

        Args:
            interview_id: Parent interview UUID.
            question_id: YAML question ID.
            round_num: Answer round (0 = initial).
        """
        self.interview_id = interview_id
        self.question_id = question_id
        self.round_num = round_num
        super().__init__(
            f"Answer not found: interview={interview_id}, "
            f"question={question_id}, round={round_num}"
        )
