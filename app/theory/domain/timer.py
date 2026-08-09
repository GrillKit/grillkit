# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Per-round timer side effects for theory tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.interview.domain.events import AnswerFeedbackEvent
from app.interview.domain.rules.feedback import timeout_feedback_for_locale
from app.interview.repositories.uow import InterviewUnitOfWork
from app.theory.domain.exceptions import TheorySectionNotFoundError

if TYPE_CHECKING:
    from app.theory.use_cases.navigate_tasks import TheoryTaskNavigation


class TaskTimer:
    """Timeout persistence for timed theory task rounds."""

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        *,
        navigation: TheoryTaskNavigation | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
            navigation: Optional navigation collaborator sharing the same uow.
        """
        self._uow = uow
        self._navigation = navigation

    def persist_timed_out_round(
        self,
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        order: int,
        locale: str,
    ) -> AnswerFeedbackEvent:
        """Save a timed-out round with zero score and advance the section.

        Args:
            interview_id: Parent interview UUID.
            question_id: Question ID from the task row.
            round_num: Follow-up round (0 = initial).
            order: Display order of the task.
            locale: Locale for timeout feedback.

        Returns:
            Feedback event for the client.
        """
        next_question_data: dict[str, Any] | None = None
        feedback_text = timeout_feedback_for_locale(locale)
        timer_remaining: int | None = None

        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            raise TheorySectionNotFoundError(interview_id)
        current = section.find_task(question_id, round_num)
        updated = section.with_timed_out_round(current.id, feedback_text)
        self._uow.theory_sections.save_aggregate(updated)

        if self._navigation is not None:
            next_question_data, timer_remaining = (
                self._navigation.advance_to_next_unanswered(
                    interview_id,
                    question_id=question_id,
                    round_num=round_num,
                )
            )

        return AnswerFeedbackEvent(
            question_id=question_id,
            order=order,
            round=round_num,
            follow_up_needed=False,
            follow_up_text=None,
            next_question=next_question_data,
            timed_out=True,
            feedback=feedback_text,
            timer_remaining_seconds=timer_remaining,
        )
