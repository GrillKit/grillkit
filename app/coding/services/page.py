# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section page context builder."""

from app.coding.schemas.page import CodingPageContext
from app.coding.services.navigation import next_task_payload
from app.coding.services.section import CodingSectionService
from app.interview.repositories.uow import InterviewUnitOfWork


class CodingPageService:
    """Build coding-specific page context for session rendering."""

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        *,
        section: CodingSectionService | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this page scope.
            section: Optional coding section service sharing the same unit of work.
        """
        self._uow = uow
        self._section = section or CodingSectionService(uow)

    def activate_timer(self, interview_id: str) -> None:
        """Start the per-task timer on the current unsubmitted coding task.

        Args:
            interview_id: Parent interview UUID.
        """
        self._section.activate_pending(interview_id)
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None or section.task_time_limit_seconds is None:
            return
        current = section.find_first_unsubmitted()
        if current is None or current.started_at is not None:
            return
        updated = section.start_timer_for_task(current.id)
        self._uow.coding_sections.save_aggregate(updated)

    def build_context(self, interview_id: str) -> CodingPageContext | None:
        """Assemble coding panel context for the interview page.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Coding page context, or None when the session has no coding section.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            return None

        current = section.find_first_unsubmitted()
        completed_tasks = sum(
            1 for task in section.tasks if task.submitted_code is not None
        )
        task_timer_enabled = (
            section.task_time_limit_seconds is not None and section.status == "active"
        )
        timer_remaining = (
            current.remaining_seconds(section.task_time_limit_seconds)
            if task_timer_enabled and current is not None
            else None
        )
        current_task = next_task_payload(current) if current is not None else None
        return CodingPageContext(
            task_count=section.task_count,
            completed_tasks=completed_tasks,
            current_task=current_task,
            current_task_row_id=current.id if current is not None else None,
            task_timer_enabled=task_timer_enabled,
            task_time_limit_seconds=section.task_time_limit_seconds,
            timer_remaining_seconds=timer_remaining,
            current_round=current.round if current is not None else 0,
            complete=section.is_complete(),
            section_status=section.status,
        )

    @staticmethod
    def build_context_for(interview_id: str) -> CodingPageContext | None:
        """Build coding page context using a short-lived unit of work.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Coding page context, or None when the session has no coding section.
        """
        with InterviewUnitOfWork() as uow:
            return CodingPageService(uow).build_context(interview_id)
