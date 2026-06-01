# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session query service.

Read-only helpers for loading sessions from the database.
"""

from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.mappers import (
    answer_read_from_domain,
    interview_read_to_domain,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.schemas.mappers import interview_read_from_orm
from app.shared.infrastructure.models import Answer, Interview


class InterviewQuery:
    """Read-only queries and view-model helpers for interview sessions."""

    @staticmethod
    def get_interview(interview_id: str) -> InterviewRead | None:
        """Retrieve an interview session by ID with answers loaded.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model with answers loaded, or None if not found.
        """
        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get(interview_id)
            if interview is None:
                return None
            return interview_read_from_orm(interview)

    @staticmethod
    def get_interview_or_raise(
        interview_id: str,
        *,
        uow: InterviewUnitOfWork | None = None,
    ) -> InterviewRead:
        """Load an interview read model or raise ``InterviewNotFoundError``.

        When ``uow`` is provided, loads from that unit of work (same DB session).
        Otherwise opens a short-lived read-only ``InterviewUnitOfWork``.

        Args:
            interview_id: The session UUID.
            uow: Optional active unit of work for transactional loads.

        Returns:
            Interview read model with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
        """
        if uow is not None:
            interview = InterviewQuery.get_orm_or_raise(interview_id, uow=uow)
            return interview_read_from_orm(interview)
        with InterviewUnitOfWork() as read_uow:
            loaded = read_uow.interviews.get(interview_id)
            if loaded is None:
                raise InterviewNotFoundError(interview_id)
            return interview_read_from_orm(loaded)

    @staticmethod
    def get_orm_or_raise(interview_id: str, *, uow: InterviewUnitOfWork) -> Interview:
        """Load an ORM interview row within an active unit of work.

        Args:
            interview_id: The session UUID.
            uow: Active unit of work.

        Returns:
            Interview ORM row with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
        """
        interview = uow.interviews.get(interview_id)
        if not interview:
            raise InterviewNotFoundError(interview_id)
        return interview

    @staticmethod
    def ensure_current_round_started(interview_id: str) -> None:
        """Start the timer on the current unanswered round when the page loads.

        Args:
            interview_id: The interview_dto UUID.
        """
        with InterviewUnitOfWork(auto_commit=True) as uow:
            interview_orm = InterviewQuery.get_orm_or_raise(interview_id, uow=uow)
            if not interview_orm.question_time_limit_seconds:
                return
            interview_dto = interview_read_from_orm(interview_orm)
            current = interview_read_to_domain(interview_dto).find_first_unanswered()
            if current is not None:
                db_answer = next(
                    a
                    for a in interview_orm.answers
                    if a.question_id == current.question_id and a.round == current.round
                )
                uow.answers.mark_started(db_answer)

    @staticmethod
    def timer_remaining_for_interview(interview: InterviewRead) -> int | None:
        """Return seconds left on the current round timer for templates.

        Args:
            interview: Interview read model with answers loaded.

        Returns:
            Remaining seconds, or None when the timer is disabled.
        """
        session = interview_read_to_domain(interview)
        current = session.find_first_unanswered()
        if current is None:
            return None
        return current.remaining_seconds(interview.question_time_limit_seconds)

    @staticmethod
    def get_current_unanswered(interview: InterviewRead) -> AnswerRead | None:
        """Return the first unanswered answer in display order.

        Args:
            interview: Interview read model with answers.

        Returns:
            The first unanswered answer read model, or None.
        """
        answer = interview_read_to_domain(interview).find_first_unanswered()
        return answer_read_from_domain(answer) if answer is not None else None

    @staticmethod
    def find_orm_answer(
        interview_orm: Interview,
        *,
        question_id: str,
        round_num: int,
    ) -> Answer:
        """Locate an answer ORM row on a loaded interview.

        Args:
            interview_orm: Interview with eager-loaded answers.
            question_id: YAML question ID.
            round_num: Follow-up round number.

        Returns:
            Matching Answer ORM instance.

        Raises:
            StopIteration: If no matching row exists (caller should handle).
        """
        return next(
            a
            for a in interview_orm.answers
            if a.question_id == question_id and a.round == round_num
        )
