# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Advance coding sections to the next unsubmitted task."""

from typing import Any

from app.coding.domain.entities import CodingSection, CodingTask
from app.coding.domain.exceptions import CodingSectionNotFoundError
from app.coding.domain.task_spec import client_task_spec_from_stored
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.phases import SessionPhaseOrchestrator


def next_task_payload(task: CodingTask) -> dict[str, Any]:
    """Build WebSocket/API payload for the next unsubmitted coding task.

    Args:
        task: Next unsubmitted coding task round.

    Returns:
        Dict with task fields for the client.
    """
    return {
        "task_id": task.task_id,
        "order": task.order,
        "round": task.round,
        "prompt_text": task.prompt_text,
        "task_spec": client_task_spec_from_stored(task.task_spec),
    }


class CodingNavigationService:
    """Shared navigation after a coding task round is completed."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    def advance_to_next_unsubmitted(
        self,
        interview_id: str,
        *,
        task_id: str,
        round_num: int,
    ) -> tuple[dict[str, Any] | None, int | None]:
        """Activate the next unsubmitted task and build client payload.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID of the completed round.
            round_num: Follow-up round that was just completed.

        Returns:
            Tuple of (next_task dict or None, timer_remaining_seconds or None).

        Raises:
            CodingSectionNotFoundError: If the coding section does not exist.
            CodingSectionNotActiveError: If the section is not active.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            raise CodingSectionNotFoundError(interview_id)

        section.ensure_active()
        current_index = next(
            i
            for i, task in enumerate(section.tasks)
            if task.task_id == task_id and task.round == round_num
        )
        next_task = section.find_next_unsubmitted_after(current_index)
        if next_task is None:
            self._notify_phase_complete_if_needed(interview_id, section)
            return None, None

        updated = section.start_timer_for_task(next_task.id)
        self._uow.coding_sections.save_aggregate(updated)
        activated = next(task for task in updated.tasks if task.id == next_task.id)
        timer_remaining = activated.remaining_seconds(updated.task_time_limit_seconds)
        return next_task_payload(activated), timer_remaining

    def _notify_phase_complete_if_needed(
        self,
        interview_id: str,
        section: CodingSection,
    ) -> None:
        """Trigger section prefetch when the coding phase has no remaining tasks.

        Args:
            interview_id: Parent interview UUID.
            section: Coding section after the latest navigation update.
        """
        if section.is_complete():
            SessionPhaseOrchestrator(self._uow).notify_section_complete(
                interview_id,
                "coding",
            )
