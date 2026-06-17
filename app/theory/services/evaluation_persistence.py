# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persist AI evaluation results and advance theory sections."""

from typing import Any

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.events import AnswerFeedbackEvent
from app.theory.domain.exceptions import TheorySectionNotFoundError
from app.theory.services.evaluator.models import (
    AnswerEvaluation,
    FollowUpEvaluation,
)
from app.theory.services.navigation import TheoryNavigationService


class TheoryEvaluationPersistenceService:
    """Save evaluation scores and advance timed theory task rounds."""

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        *,
        navigation: TheoryNavigationService | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
            navigation: Optional navigation collaborator sharing the same uow.
        """
        self._uow = uow
        self._navigation = navigation or TheoryNavigationService(uow)

    def advance_without_evaluation(
        self,
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        order: int,
    ) -> AnswerFeedbackEvent:
        """Advance the section without waiting for AI evaluation.

        Args:
            interview_id: Parent interview UUID.
            question_id: Question ID from the task row.
            round_num: Follow-up round that was just answered.
            order: Display order of the task.

        Returns:
            Feedback event for the client with the next question, if any.
        """
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
            timer_remaining_seconds=timer_remaining,
        )

    def persist_evaluation_only(
        self,
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        evaluation: AnswerEvaluation | FollowUpEvaluation,
    ) -> None:
        """Persist AI score and feedback for one task round.

        Args:
            interview_id: Parent interview UUID.
            question_id: Question ID from the task row.
            round_num: Follow-up round that was evaluated.
            evaluation: Parsed AI evaluation.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            raise TheorySectionNotFoundError(interview_id)
        updated = section.with_evaluation(
            question_id,
            round_num,
            evaluation.score,
            evaluation.feedback,
        )
        self._uow.theory_sections.save_aggregate(updated)

    def persist(
        self,
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
            interview_id: Parent interview UUID.
            question_id: Question ID from the task row.
            round_num: Follow-up round (0 = initial).
            order: Display order of the task.
            evaluation: Parsed AI evaluation.
            follow_up_needed: Whether to create a follow-up row.
            follow_up_text: Follow-up question text when applicable.

        Returns:
            Feedback event for the client.
        """
        next_question_data: dict[str, Any] | None = None
        timer_remaining: int | None = None
        follow_up_answer_id: int | None = None

        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            raise TheorySectionNotFoundError(interview_id)
        section.ensure_active()

        updated = section.with_evaluation(
            question_id,
            round_num,
            evaluation.score,
            evaluation.feedback,
        )
        follow_up_round: int | None = None
        if follow_up_needed:
            updated, pending = updated.with_follow_up(question_id, follow_up_text or "")
            follow_up_round = pending.round

        self._uow.theory_sections.save_aggregate(updated)

        if follow_up_needed and follow_up_round is not None:
            self._uow.flush()
            reloaded = self._uow.theory_sections.get_aggregate(interview_id)
            if reloaded is None:
                raise TheorySectionNotFoundError(interview_id)
            follow_up = reloaded.find_task(question_id, follow_up_round)
            follow_up_answer_id = follow_up.id
            timed = reloaded.start_timer_for_task(follow_up.id)
            self._uow.theory_sections.save_aggregate(timed)
            activated = next(task for task in timed.tasks if task.id == follow_up.id)
            timer_remaining = activated.remaining_seconds(timed.task_time_limit_seconds)
        else:
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
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
            next_question=next_question_data,
            timer_remaining_seconds=timer_remaining,
            follow_up_answer_id=follow_up_answer_id,
        )
