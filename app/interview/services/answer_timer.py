# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Per-round timer side effects for interview answers."""

from typing import Any

from app.interview.domain.entities import Answer, Interview
from app.interview.repositories.mappers import answer_from_orm
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.events import AnswerFeedbackEvent
from app.interview.services.session_navigation import SessionNavigationService
from app.shared.infrastructure.models import Answer as OrmAnswer
from app.shared.infrastructure.models import Interview as OrmInterview


class RoundTimerService:
    """Timer activation and timeout persistence for answer rounds."""

    @staticmethod
    def activate_timed_round(
        uow: InterviewUnitOfWork, interview: OrmInterview, answer: OrmAnswer | None
    ) -> None:
        """Start the per-round timer on an answer row when the session has a limit.

        Args:
            uow: Active unit of work.
            interview: Parent interview.
            answer: Answer row that became current, if any.
        """
        if interview.question_time_limit_seconds and answer is not None:
            uow.answers.mark_started(answer)

    @staticmethod
    def remaining_for_answer(
        interview: OrmInterview, answer: OrmAnswer | None
    ) -> int | None:
        """Return seconds left on the current round timer.

        Args:
            interview: Parent interview.
            answer: Current answer row.

        Returns:
            Remaining seconds, or None when the timer is disabled.
        """
        if answer is None:
            return None
        return answer_from_orm(answer).remaining_seconds(
            interview.question_time_limit_seconds
        )

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
        feedback_text = Interview.timeout_feedback(locale)
        timer_remaining: int | None = None

        with InterviewUnitOfWork(auto_commit=True) as uow:
            db_answer = uow.answers.get_by_interview_question_round(
                interview_id=interview_id,
                question_id=question_id,
                round_num=round_num,
            )
            uow.answers.set_answer_text(db_answer, Answer.TIME_EXPIRED_ANSWER_TEXT)
            uow.answers.set_evaluation(db_answer, 0, feedback_text)

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
