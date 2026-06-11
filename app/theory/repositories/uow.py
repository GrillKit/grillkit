# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory feature unit of work with repository accessors."""

from __future__ import annotations

from app.shared.infrastructure.uow import UnitOfWork
from app.theory.repositories.theory_section import TheorySectionRepository


class TheoryUnitOfWork(UnitOfWork):
    """Unit of Work exposing the theory section repository.

    Usage::

        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            uow.commit()
    """

    def __init__(self, auto_commit: bool = False) -> None:
        """Initialize the theory unit of work.

        Args:
            auto_commit: If True, commit on successful context exit.
        """
        super().__init__(auto_commit=auto_commit)
        self._theory_sections_repo: TheorySectionRepository | None = None

    @property
    def theory_sections(self) -> TheorySectionRepository:
        """Access the ``TheorySectionRepository`` bound to this UoW."""
        if self._theory_sections_repo is None:
            self._theory_sections_repo = TheorySectionRepository(self.session)
        return self._theory_sections_repo
