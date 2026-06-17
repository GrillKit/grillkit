# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Build coding session state read models for the interview UI."""

from __future__ import annotations

from app.coding.domain.entities import CodeRunAttempt, CodingTask
from app.coding.domain.exceptions import CodingSectionNotFoundError
from app.coding.domain.task_spec import client_task_spec_from_stored
from app.coding.schemas.coding import (
    CodeRunAttemptRead,
    CodingSessionStateRead,
    CodingTaskStateRead,
)
from app.interview.repositories.uow import InterviewUnitOfWork


def _task_state_from_domain(task: CodingTask) -> CodingTaskStateRead:
    """Map a domain coding task to a client-safe state row.

    Args:
        task: Domain coding task entity.

    Returns:
        Task state read model for the coding panel.
    """
    return CodingTaskStateRead(
        id=task.id,
        task_id=task.task_id,
        order=task.order,
        round=task.round,
        prompt_text=task.prompt_text,
        task_spec=client_task_spec_from_stored(task.task_spec),
        submitted_code=task.submitted_code,
        score=task.score,
        feedback=task.feedback,
        started_at=task.started_at,
    )


def _attempt_state_from_domain(attempt: CodeRunAttempt) -> CodeRunAttemptRead:
    """Map a domain run attempt to an API read model.

    Args:
        attempt: Persisted run attempt entity.

    Returns:
        Run attempt read model for clients.
    """
    return CodeRunAttemptRead(
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        stdout=attempt.stdout,
        stderr=attempt.stderr,
        compile_output=attempt.compile_output,
        tests_passed=attempt.tests_passed,
        tests_total=attempt.tests_total,
        test_results=list(attempt.test_results),
        duration_ms=attempt.duration_ms,
        created_at=attempt.created_at,
    )


class CodingStateService:
    """Read-only builder for ``GET /coding/state`` responses."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work."""
        self._uow = uow

    def get_state(self, interview_id: str) -> CodingSessionStateRead:
        """Return coding section progress and recent Run attempts.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Session state for the coding panel.

        Raises:
            CodingSectionNotFoundError: If no coding section exists.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            raise CodingSectionNotFoundError(interview_id)

        current_task = section.find_first_unsubmitted()
        current_task_state = (
            _task_state_from_domain(current_task) if current_task is not None else None
        )
        run_attempts: tuple[CodeRunAttemptRead, ...] = ()
        if current_task is not None:
            attempts = self._uow.code_run_attempts.list_for_task(current_task.id)
            run_attempts = tuple(
                _attempt_state_from_domain(attempt) for attempt in attempts
            )

        completed_tasks = sum(
            1 for task in section.tasks if task.submitted_code is not None
        )
        return CodingSessionStateRead(
            interview_id=interview_id,
            section_status=section.status,
            task_time_limit_seconds=section.task_time_limit_seconds,
            completed_tasks=completed_tasks,
            total_tasks=section.task_count,
            current_task=current_task_state,
            tasks=[_task_state_from_domain(task) for task in section.tasks],
            run_attempts=list(run_attempts),
        )
