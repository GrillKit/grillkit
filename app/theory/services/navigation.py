# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Advance theory sections to the next unanswered task."""

from typing import Any

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.phases import SessionPhaseOrchestrator
from app.theory.domain.entities import TheorySection, TheoryTask
from app.theory.domain.exceptions import TheorySectionNotFoundError


def next_task_payload(task: TheoryTask) -> dict[str, Any]:
    """Build WebSocket/API payload for the next unanswered task.

    Args:
        task: Next unanswered theory task round.

    Returns:
        Dict with question fields for the client.
    """
    return {
        "id": task.id,
        "question_id": task.question_id,
        "order": task.order,
        "question_text": task.question_text,
        "question_code": task.question_code,
        "round": task.round,
    }


class TheoryNavigationService:
    """Shared navigation after a theory task round is completed or timed out."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    def advance_to_next_unanswered(
        self,
        interview_id: str,
        *,
        question_id: str,
        round_num: int,
    ) -> tuple[dict[str, Any] | None, int | None]:
        """Activate the next unanswered task and build client payload.

        Args:
            interview_id: Parent interview UUID.
            question_id: Question ID of the completed round.
            round_num: Follow-up round that was just completed.

        Returns:
            Tuple of (next_question dict or None, timer_remaining_seconds or None).

        Raises:
            TheorySectionNotFoundError: If the theory section does not exist.
            TheorySectionNotActiveError: If the section is not active.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            raise TheorySectionNotFoundError(interview_id)

        section.ensure_active()

        current_index = next(
            i
            for i, task in enumerate(section.tasks)
            if task.question_id == question_id and task.round == round_num
        )
        next_task = section.find_next_unanswered_after(current_index)
        if next_task is None:
            self._notify_phase_complete_if_needed(interview_id, section)
            return None, None

        updated = section.start_timer_for_task(next_task.id)
        self._uow.theory_sections.save_aggregate(updated)

        activated = next(task for task in updated.tasks if task.id == next_task.id)
        timer_remaining = activated.remaining_seconds(updated.task_time_limit_seconds)
        return next_task_payload(activated), timer_remaining

    def _notify_phase_complete_if_needed(
        self,
        interview_id: str,
        section: TheorySection,
    ) -> None:
        """Trigger section prefetch when the theory phase has no remaining tasks.

        Args:
            interview_id: Parent interview UUID.
            section: Theory section after the latest navigation update.
        """
        if section.is_complete():
            SessionPhaseOrchestrator(self._uow).notify_section_complete(
                interview_id,
                "theory",
            )
