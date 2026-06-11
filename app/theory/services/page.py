# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section page context builder."""

from app.interview.schemas.interview import InterviewRead
from app.interview.services.query import InterviewQuery
from app.theory.repositories.uow import TheoryUnitOfWork
from app.theory.schemas.page import TheoryPageContext


class TheoryPageService:
    """Build theory-specific page context for session rendering."""

    @staticmethod
    def activate_timer(interview_id: str) -> None:
        """Start the per-round timer on the current unanswered theory task.

        Args:
            interview_id: Parent interview UUID.
        """
        with TheoryUnitOfWork(auto_commit=True) as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None or section.task_time_limit_seconds is None:
                return
            current = section.find_first_unanswered()
            if current is None or current.started_at is not None:
                return
            updated = section.start_timer_for_task(current.id)
            uow.theory_sections.save_aggregate(updated)

    @staticmethod
    def _timer_remaining_seconds(interview_id: str) -> int | None:
        """Return seconds left on the current theory task timer.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Remaining seconds, or None when the timer is disabled or unavailable.
        """
        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                return None
            current = section.find_first_unanswered()
            if current is None:
                return None
            return current.remaining_seconds(section.task_time_limit_seconds)

    @staticmethod
    def build_context(interview: InterviewRead) -> TheoryPageContext | None:
        """Assemble theory panel context from a loaded interview read model.

        Args:
            interview: Interview read model with theory tasks mirrored as answers.

        Returns:
            Theory page context, or None when the session has no theory tasks.
        """
        if not interview.answers:
            with TheoryUnitOfWork() as uow:
                section = uow.theory_sections.get_aggregate(interview.id)
                if section is None:
                    return None

        current_question = InterviewQuery.get_current_unanswered(interview)
        question_timer_enabled = interview.question_time_limit_seconds is not None
        timer_remaining_seconds = (
            TheoryPageService._timer_remaining_seconds(interview.id)
            if question_timer_enabled
            else None
        )
        current_round = current_question.round if current_question else 0
        complete = current_question is None and bool(interview.answers)

        return TheoryPageContext(
            answers=interview.answers,
            current_question=current_question,
            current_answer_id=current_question.id if current_question else None,
            question_timer_enabled=question_timer_enabled,
            question_time_limit_seconds=interview.question_time_limit_seconds,
            timer_remaining_seconds=timer_remaining_seconds,
            current_round=current_round,
            complete=complete,
        )

    @staticmethod
    def load_interview(interview_id: str) -> InterviewRead | None:
        """Load interview read model and activate the theory timer when needed.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Interview read model, or None when not found.
        """
        TheoryPageService.activate_timer(interview_id)
        return InterviewQuery.get_interview(interview_id)
