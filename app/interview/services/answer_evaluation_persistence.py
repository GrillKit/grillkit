# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persist AI evaluation results and advance interview sessions."""

from typing import Any

from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.evaluator.service import (
    AnswerEvaluation,
    FollowUpEvaluation,
)
from app.interview.services.events import AnswerFeedbackEvent
from app.interview.services.session_navigation import SessionNavigationService


class AnswerEvaluationPersistenceService:
    """Save evaluation scores and advance timed interview rounds."""

    @staticmethod
    def advance_without_evaluation(
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        order: int,
    ) -> AnswerFeedbackEvent:
        """Advance the session without waiting for AI evaluation.

        Used when the user submits the last allowed follow-up round: navigation
        happens immediately while score and feedback are persisted separately.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the answer row.
            round_num: Follow-up round that was just answered.
            order: Display order of the answer.

        Returns:
            Feedback event for the client with the next question, if any.
        """
        next_question_data: dict[str, Any] | None = None
        timer_remaining: int | None = None

        with InterviewUnitOfWork(auto_commit=True) as uow:
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
            timer_remaining_seconds=timer_remaining,
        )

    @staticmethod
    def persist_evaluation_only(
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        evaluation: AnswerEvaluation | FollowUpEvaluation,
    ) -> None:
        """Persist AI score and feedback for one answer round.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the answer row.
            round_num: Follow-up round that was evaluated.
            evaluation: Parsed AI evaluation.
        """
        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            updated = aggregate.with_evaluation(
                question_id,
                round_num,
                evaluation.score,
                evaluation.feedback,
            )
            uow.interviews.save_aggregate(updated)

    @staticmethod
    def persist(
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        order: int,
        evaluation: AnswerEvaluation | FollowUpEvaluation,
        follow_up_needed: bool,
        follow_up_text: str | None,
    ) -> AnswerFeedbackEvent:
        """Save AI evaluation results and build a feedback event.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the answer row.
            round_num: Follow-up round (0 = initial).
            order: Display order of the answer.
            evaluation: Parsed AI evaluation.
            follow_up_needed: Whether to create a follow-up row.
            follow_up_text: Follow-up question text when applicable.

        Returns:
            Feedback event for the client.
        """
        next_question_data: dict[str, Any] | None = None
        timer_remaining: int | None = None

        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            aggregate.ensure_active()

            updated = aggregate.with_evaluation(
                question_id,
                round_num,
                evaluation.score,
                evaluation.feedback,
            )
            follow_up_round: int | None = None
            if follow_up_needed:
                updated, pending = updated.with_follow_up(
                    question_id, follow_up_text or ""
                )
                follow_up_round = pending.round

            uow.interviews.save_aggregate(updated)

            if follow_up_needed and follow_up_round is not None:
                uow.flush()
                reloaded = uow.interviews.get_aggregate(interview_id)
                if reloaded is None:
                    raise InterviewNotFoundError(interview_id)
                follow_up = reloaded.find_answer(question_id, follow_up_round)
                timed = reloaded.start_timer_for_answer(follow_up.id)
                uow.interviews.save_aggregate(timed)
                activated = next(
                    answer for answer in timed.answers if answer.id == follow_up.id
                )
                timer_remaining = activated.remaining_seconds(
                    timed.question_time_limit_seconds
                )
            else:
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
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
            next_question=next_question_data,
            timer_remaining_seconds=timer_remaining,
        )
