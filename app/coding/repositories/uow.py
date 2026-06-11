# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding feature unit of work with repository accessors."""

from __future__ import annotations

from app.coding.repositories.code_run_attempt import CodeRunAttemptRepository
from app.coding.repositories.coding_section import CodingSectionRepository
from app.shared.infrastructure.uow import UnitOfWork


class CodingUnitOfWork(UnitOfWork):
    """Unit of Work exposing the coding section repository.

    Usage::

        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            uow.commit()
    """

    def __init__(self, auto_commit: bool = False) -> None:
        """Initialize the coding unit of work.

        Args:
            auto_commit: If True, commit on successful context exit.
        """
        super().__init__(auto_commit=auto_commit)
        self._coding_sections_repo: CodingSectionRepository | None = None
        self._code_run_attempts_repo: CodeRunAttemptRepository | None = None

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
