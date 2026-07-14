# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section creation service."""

from app.coding.domain.entities import CodingSection, CodingSectionStatus
from app.coding.domain.value_objects import PlannedCodingTask
from app.interview.domain.value_objects import InterviewSelection
from app.interview.repositories.uow import InterviewUnitOfWork


class CodingSectionCreationService:
    """Service for creating coding sections within an interview session."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    def create(
        self,
        interview_id: str,
        *,
        selection: InterviewSelection,
        locale: str,
        planned_tasks: tuple[PlannedCodingTask, ...],
        task_time_limit_seconds: int | None,
        status: CodingSectionStatus = "active",
    ) -> CodingSection:
        """Persist a coding section with initial task rows.

        Args:
            interview_id: Parent interview UUID.
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback.
            planned_tasks: Ordered tasks for this section.
            task_time_limit_seconds: Per-task time limit, or None to disable.
            status: Initial section status (``pending`` until phase switch).

        Returns:
            Persisted coding section aggregate with assigned task IDs.

        Raises:
            ValueError: If ``planned_tasks`` is empty.
        """
        section = CodingSection.start(
            interview_id,
            selection=selection,
            locale=locale,
            planned_tasks=planned_tasks,
            task_time_limit_seconds=task_time_limit_seconds,
            status=status,
        )
        return self._uow.coding_sections.create_aggregate(section)
