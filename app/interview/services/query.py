# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session query service.

Read-only helpers for loading sessions from the database.
"""

from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.read_model import load_interview_read


class InterviewQuery:
    """Read-only queries and view-model helpers for interview sessions."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this read scope.
        """
        self._uow = uow

    def get_interview(self, interview_id: str) -> InterviewRead | None:
        """Retrieve an interview session by ID with theory tasks loaded.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model with answers loaded, or None if not found.
        """
        return load_interview_read(self._uow, interview_id)

    @staticmethod
    def load(interview_id: str) -> InterviewRead | None:
        """Load an interview read model using a short-lived unit of work.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model with answers loaded, or None if not found.
        """
        with InterviewUnitOfWork() as uow:
            return InterviewQuery(uow).get_interview(interview_id)

    def get_active_or_raise(self, interview_id: str) -> InterviewRead:
        """Load an active interview read model or raise a domain error.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is not active.
        """
        shell = self._uow.interviews.get_aggregate(interview_id)
        if shell is None:
            raise InterviewNotFoundError(interview_id)
        shell.ensure_active()
        interview = self.get_interview(interview_id)
        if interview is None:
            raise InterviewNotFoundError(interview_id)
        return interview

    @staticmethod
    def get_active_interview_or_raise(interview_id: str) -> InterviewRead:
        """Load an active interview using a short-lived unit of work.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is not active.
        """
        with InterviewUnitOfWork() as uow:
            return InterviewQuery(uow).get_active_or_raise(interview_id)

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
