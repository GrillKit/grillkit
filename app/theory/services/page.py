# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section page context builder."""

from app.interview.domain.serialization import parse_session_spec
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.services.query import InterviewQuery
from app.theory.schemas.page import TheoryPageContext


class TheoryPageService:
    """Build theory-specific page context for session rendering."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this page scope.
        """
        self._uow = uow

    def activate_timer(self, interview_id: str) -> None:
        """Start the per-round timer on the current unanswered theory task.

        Args:
            interview_id: Parent interview UUID.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None or section.task_time_limit_seconds is None:
            return
        current = section.find_first_unanswered()
        if current is None or current.started_at is not None:
            return
        updated = section.start_timer_for_task(current.id)
        self._uow.theory_sections.save_aggregate(updated)

    def build_context(self, interview: InterviewRead) -> TheoryPageContext | None:
        """Assemble theory panel context from a loaded interview read model.

        Args:
            interview: Interview read model with theory tasks mirrored as answers.

        Returns:
            Theory page context, or None when the session has no theory tasks.
        """
        session = parse_session_spec(
            interview.selection_spec,
            question_count=interview.question_count,
            task_time_limit_seconds=interview.question_time_limit_seconds,
        )
        if not session.theory.enabled:
            return None

        section = self._uow.theory_sections.get_aggregate(interview.id)
        if section is None and not interview.answers:
            return None

        current_question = InterviewQuery.get_current_unanswered(interview)
        question_timer_enabled = interview.question_time_limit_seconds is not None
        timer_remaining_seconds = None
        if question_timer_enabled and section is not None:
            current = section.find_first_unanswered()
            if current is not None:
                timer_remaining_seconds = current.remaining_seconds(
                    section.task_time_limit_seconds
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
    def build_context_for(interview: InterviewRead) -> TheoryPageContext | None:
        """Build theory page context using a short-lived unit of work.

        Args:
            interview: Interview read model with theory tasks mirrored as answers.

        Returns:
            Theory page context, or None when the session has no theory tasks.
        """
        with InterviewUnitOfWork() as uow:
            return TheoryPageService(uow).build_context(interview)
