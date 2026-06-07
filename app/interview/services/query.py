# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session query service.

Read-only helpers for loading sessions from the database.
"""

from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.mappers import interview_to_read
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import AnswerRead, InterviewRead


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
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                return None
            return interview_to_read(aggregate)

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
            aggregate = uow.interviews.get_aggregate(interview_id)
        else:
            with InterviewUnitOfWork() as read_uow:
                aggregate = read_uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            raise InterviewNotFoundError(interview_id)
        return interview_to_read(aggregate)

    @staticmethod
    def get_active_interview_or_raise(interview_id: str) -> InterviewRead:
        """Load an active interview read model or raise a domain error.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is not active.
        """
        with InterviewUnitOfWork() as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            aggregate.ensure_active()
            return interview_to_read(aggregate)

    @staticmethod
    def timer_remaining_seconds(interview_id: str) -> int | None:
        """Return seconds left on the current round timer for templates.

        Args:
            interview_id: The session UUID.

        Returns:
            Remaining seconds, or None when the timer is disabled or unavailable.
        """
        with InterviewUnitOfWork() as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                return None
            current = aggregate.find_first_unanswered()
            if current is None:
                return None
            return current.remaining_seconds(aggregate.question_time_limit_seconds)

    @staticmethod
    def get_current_unanswered(interview: InterviewRead) -> AnswerRead | None:
        """Return the first unanswered answer in display order.

        Args:
            interview: Interview read model with answers.

        Returns:
            The first unanswered answer read model, or None.
        """
        for answer in interview.answers:
            if answer.answer_text is None:
                return answer
        return None
