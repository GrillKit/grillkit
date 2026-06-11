# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Per-round timer side effects for theory tasks."""

from typing import Any

from app.interview.services.events import AnswerFeedbackEvent
from app.interview.services.rules.feedback import timeout_feedback_for_locale
from app.theory.domain.exceptions import TheorySectionNotFoundError
from app.theory.repositories.uow import TheoryUnitOfWork
from app.theory.services.navigation import TheoryNavigationService


class TheoryTimerService:
    """Timeout persistence for timed theory task rounds."""

    @staticmethod
    def persist_timed_out_round(
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

        with TheoryUnitOfWork(auto_commit=True) as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                raise TheorySectionNotFoundError(interview_id)
            current = section.find_task(question_id, round_num)
            updated = section.with_timed_out_round(current.id, feedback_text)
            uow.theory_sections.save_aggregate(updated)

            next_question_data, timer_remaining = (
                TheoryNavigationService.advance_to_next_unanswered(
                    uow,
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
