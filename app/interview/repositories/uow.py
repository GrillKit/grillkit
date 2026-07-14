# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Application-wide unit of work with repository accessors."""

from __future__ import annotations

from app.coding.repositories.code_run_attempt import CodeRunAttemptRepository
from app.coding.repositories.coding_section import CodingSectionRepository
from app.interview.repositories.interview import InterviewRepository
from app.interview.repositories.known_questions import KnownQuestionsRepository
from app.shared.infrastructure.uow import UnitOfWork
from app.theory.repositories.theory_section import TheorySectionRepository


class InterviewUnitOfWork(UnitOfWork):
    """Unit of Work for interview shell and all section persistence.

    Usage::

        with InterviewUnitOfWork() as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            completed = aggregate.with_session_completed({"summary": "..."})
            uow.interviews.save_aggregate(completed)
            uow.commit()
    """

    def __init__(self, auto_commit: bool = False) -> None:
        """Initialize the application unit of work.

        Args:
            auto_commit: If True, commit on successful context exit.
        """
        super().__init__(auto_commit=auto_commit)
        self._interviews_repo: InterviewRepository | None = None
        self._theory_sections_repo: TheorySectionRepository | None = None
        self._coding_sections_repo: CodingSectionRepository | None = None
        self._code_run_attempts_repo: CodeRunAttemptRepository | None = None
        self._known_questions_repo: KnownQuestionsRepository | None = None

    @property
    def interviews(self) -> InterviewRepository:
        """Access the ``InterviewRepository`` bound to this UoW."""
        if self._interviews_repo is None:
            self._interviews_repo = InterviewRepository(self.session)
        return self._interviews_repo

    @property
    def theory_sections(self) -> TheorySectionRepository:
        """Access the ``TheorySectionRepository`` bound to this UoW."""
        if self._theory_sections_repo is None:
            self._theory_sections_repo = TheorySectionRepository(self.session)
        return self._theory_sections_repo

    @property
    def coding_sections(self) -> CodingSectionRepository:
        """Access the ``CodingSectionRepository`` bound to this UoW."""
        if self._coding_sections_repo is None:
            self._coding_sections_repo = CodingSectionRepository(self.session)
        return self._coding_sections_repo

    @property
    def code_run_attempts(self) -> CodeRunAttemptRepository:
        """Access the ``CodeRunAttemptRepository`` bound to this UoW."""
        if self._code_run_attempts_repo is None:
            self._code_run_attempts_repo = CodeRunAttemptRepository(self.session)
        return self._code_run_attempts_repo

    @property
    def known_questions(self) -> KnownQuestionsRepository:
        """Access the ``KnownQuestionsRepository`` bound to this UoW."""
        if self._known_questions_repo is None:
            self._known_questions_repo = KnownQuestionsRepository(self.session)
        return self._known_questions_repo
