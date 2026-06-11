# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section page context builder."""

from app.coding.repositories.uow import CodingUnitOfWork
from app.coding.schemas.page import CodingPageContext
from app.coding.services.navigation import next_task_payload
from app.coding.services.section import CodingSectionService


class CodingPageService:
    """Build coding-specific page context for session rendering."""

    @staticmethod
    def activate_timer(interview_id: str) -> None:
        """Start the per-task timer on the current unsubmitted coding task.

        Args:
            interview_id: Parent interview UUID.
        """
        CodingSectionService.activate_pending(interview_id)
        with CodingUnitOfWork(auto_commit=True) as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None or section.task_time_limit_seconds is None:
                return
            current = section.find_first_unsubmitted()
            if current is None or current.started_at is not None:
                return
            updated = section.start_timer_for_task(current.id)
            uow.coding_sections.save_aggregate(updated)

    @staticmethod
    def build_context(interview_id: str) -> CodingPageContext | None:
        """Assemble coding panel context for the interview page.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Coding page context, or None when the session has no coding section.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return None

            current = section.find_first_unsubmitted()
            completed_tasks = sum(
                1 for task in section.tasks if task.submitted_code is not None
            )
            task_timer_enabled = section.task_time_limit_seconds is not None
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
