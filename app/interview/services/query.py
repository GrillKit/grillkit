# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session query service.

Read-only helpers for loading sessions from the database.
"""

from app.interview.domain.progress import find_first_unanswered
from app.interview.domain.session import AnswerView, interview_view
from app.interview.domain.timer import remaining_seconds
from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.domain.exceptions import InterviewNotFoundError
from app.shared.infrastructure.models import Interview


class InterviewQuery:
    """Read-only queries and view-model helpers for interview sessions."""

    @staticmethod
    def get_interview(interview_id: str) -> Interview | None:
        """Retrieve an interview session by ID with answers loaded.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview with answers loaded, or None if not found.
        """
        with InterviewUnitOfWork() as uow:
            return uow.interviews.get(interview_id)

    @staticmethod
    def get_interview_or_raise(
        interview_id: str,
        *,
        uow: InterviewUnitOfWork | None = None,
    ) -> Interview:
        """Load an interview or raise ``InterviewNotFoundError``.

        When ``uow`` is provided, loads from that unit of work (same DB session).
        Otherwise opens a short-lived read-only ``InterviewUnitOfWork``.

        Args:
            interview_id: The session UUID.
            uow: Optional active unit of work for transactional loads.

        Returns:
            Interview with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
        """
        if uow is not None:
            interview = uow.interviews.get(interview_id)
        else:
            with InterviewUnitOfWork() as uow:
                interview = uow.interviews.get(interview_id)
        if not interview:
            raise InterviewNotFoundError(interview_id)
        return interview

    @staticmethod
    def ensure_current_round_started(interview_id: str) -> None:
        """Start the timer on the current unanswered round when the page loads.

        Args:
            interview_id: The session UUID.
        """
        with InterviewUnitOfWork(auto_commit=True) as uow:
            interview = InterviewQuery.get_interview_or_raise(interview_id, uow=uow)
            if not interview.question_time_limit_seconds:
                return
            session = interview_view(interview)
            current = find_first_unanswered(session)
            if current is not None:
                db_answer = next(
                    a
                    for a in interview.answers
                    if a.question_id == current.question_id and a.round == current.round
                )
                uow.answers.mark_started(db_answer)

    @staticmethod
    def timer_remaining_for_interview(interview: Interview) -> int | None:
        """Return seconds left on the current round timer for templates.

        Args:
            interview: Interview with answers loaded.

        Returns:
            Remaining seconds, or None when the timer is disabled.
        """
        session = interview_view(interview)
        current = find_first_unanswered(session)
        if current is None:
            return None
        return remaining_seconds(
            current.started_at,
            interview.question_time_limit_seconds,
        )

    @staticmethod
    def get_current_unanswered(interview: Interview) -> AnswerView | None:
        """Return the first unanswered answer in display order.

        Args:
            interview: Interview with eager-loaded answers.

        Returns:
            The first unanswered answer view, or None.
        """
        return find_first_unanswered(interview_view(interview))
