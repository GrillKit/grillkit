# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding domain exceptions."""


class CodingDomainError(Exception):
    """Base class for coding-related domain errors."""


class CodingSectionNotFoundError(CodingDomainError):
    """Raised when a coding section does not exist for an interview."""

    def __init__(self, interview_id: str) -> None:
        """Initialize with the parent interview ID.

        Args:
            interview_id: Parent interview UUID.
        """
        self.interview_id = interview_id
        super().__init__(f"Coding section not found for interview: {interview_id}")


class CodingSectionNotActiveError(CodingDomainError):
    """Raised when an operation requires an active coding section."""

    def __init__(self, interview_id: str | None = None) -> None:
        """Initialize optionally with the interview ID.

        Args:
            interview_id: Parent interview UUID, if known.
        """
        self.interview_id = interview_id
        super().__init__("Cannot submit code to a completed coding section")


class CodingTaskNotCurrentError(CodingDomainError):
    """Raised when Run/Submit targets a task that is not the active round."""

    def __init__(self, interview_id: str, task_id: str) -> None:
        """Initialize with lookup keys.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID from the client request.
        """
        self.interview_id = interview_id
        self.task_id = task_id
        super().__init__(
            f"Task {task_id} is not the current coding task for interview {interview_id}"
        )


class CodingRunLimitExceededError(CodingDomainError):
    """Raised when a task exceeds the configured Run attempt limit."""

    def __init__(self, task_id: str, limit: int) -> None:
        """Initialize with the task ID and configured limit.

        Args:
            task_id: YAML task ID.
            limit: Maximum allowed Run attempts per task.
        """
        self.task_id = task_id
        self.limit = limit
        super().__init__(f"Run limit exceeded for task {task_id} (max {limit})")


class CodingEvaluatorNotAvailableError(CodingDomainError):
    """Raised when AI evaluation is requested before the evaluator is wired."""

    def __init__(self) -> None:
        """Initialize with a stable client-facing message."""
        super().__init__("Coding AI evaluation is not available yet")


class CodingTaskNotFoundError(CodingDomainError):
    """Raised when a specific coding task row is missing."""

    def __init__(self, interview_id: str, task_id: str, round_num: int) -> None:
        """Initialize with lookup keys.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID.
            round_num: Task round (0 = initial).
        """
        self.interview_id = interview_id
        self.task_id = task_id
        self.round_num = round_num
        super().__init__(
            f"Coding task not found: interview={interview_id}, "
            f"task={task_id}, round={round_num}"
        )
