# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview feature unit of work with repository accessors."""

from __future__ import annotations

from app.interview.repositories.answer import AnswerRepository
from app.interview.repositories.interview import InterviewRepository
from app.shared.infrastructure.uow import UnitOfWork


class InterviewUnitOfWork(UnitOfWork):
    """Unit of Work exposing interview and answer repositories.

    Usage::

        with InterviewUnitOfWork() as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            completed = aggregate.with_session_completed({"summary": "..."})
            uow.interviews.save_aggregate(completed)
            uow.commit()
    """

    def __init__(self, auto_commit: bool = False) -> None:
        """Initialize the interview unit of work.

        Args:
            auto_commit: If True, commit on successful context exit.
        """
        super().__init__(auto_commit=auto_commit)
        self._interviews_repo: InterviewRepository | None = None
        self._answers_repo: AnswerRepository | None = None

    @property
    def interviews(self) -> InterviewRepository:
        """Access the ``InterviewRepository`` bound to this UoW."""
        if self._interviews_repo is None:
            self._interviews_repo = InterviewRepository(self.session)
        return self._interviews_repo

    @property
    def answers(self) -> AnswerRepository:
        """Access the ``AnswerRepository`` bound to this UoW."""
        if self._answers_repo is None:
            self._answers_repo = AnswerRepository(self.session)
        return self._answers_repo
