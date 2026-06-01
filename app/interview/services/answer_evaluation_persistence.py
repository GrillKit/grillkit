# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persist AI evaluation results and advance interview sessions."""

from typing import Any

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.answer_timer import RoundTimerService
from app.interview.services.evaluator.service import (
    AnswerEvaluation,
    FollowUpEvaluation,
)
from app.interview.services.events import AnswerFeedbackEvent
from app.interview.services.query import InterviewQuery
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
            db_answer = uow.answers.get_by_interview_question_round(
                interview_id=interview_id,
                question_id=question_id,
                round_num=round_num,
            )
            uow.answers.set_evaluation(db_answer, evaluation.score, evaluation.feedback)

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
            db_interview = InterviewQuery.get_orm_or_raise(interview_id, uow=uow)

            db_answer = uow.answers.get_by_interview_question_round(
                interview_id=interview_id,
                question_id=question_id,
                round_num=round_num,
            )
            uow.answers.set_evaluation(db_answer, evaluation.score, evaluation.feedback)

            if follow_up_needed:
                max_round = uow.answers.get_max_round(interview_id, question_id)
                follow_up = uow.answers.add_follow_up(
                    interview_id=interview_id,
                    question_id=question_id,
                    round_num=max_round + 1,
                    question_text=follow_up_text or "",
                )
                uow.flush()
                RoundTimerService.activate_timed_round(uow, db_interview, follow_up)
                timer_remaining = RoundTimerService.remaining_for_answer(
                    db_interview, follow_up
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
