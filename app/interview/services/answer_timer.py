# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Per-round timer side effects for interview answers."""

from typing import Any

from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.events import AnswerFeedbackEvent
from app.interview.services.rules.feedback import timeout_feedback_for_locale
from app.interview.services.session_navigation import SessionNavigationService


class RoundTimerService:
    """Timeout persistence for timed answer rounds."""

    @staticmethod
    def persist_timed_out_round(
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        order: int,
        locale: str,
    ) -> AnswerFeedbackEvent:
        """Save a timed-out round with zero score and advance the session.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the answer row.
            round_num: Follow-up round (0 = initial).
            order: Display order of the answer.
            locale: Locale for timeout feedback.

        Returns:
            Feedback event for the client.
        """
        next_question_data: dict[str, Any] | None = None
        feedback_text = timeout_feedback_for_locale(locale)
        timer_remaining: int | None = None

        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            current = aggregate.find_answer(question_id, round_num)
            updated = aggregate.with_timed_out_round(current.id, feedback_text)
            uow.interviews.save_aggregate(updated)

            next_question_data, timer_remaining = (
                SessionNavigationService.advance_to_next_unanswered(
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
