# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit of Work pattern for atomic database transactions.

Provides a ``UnitOfWork`` context manager that coordinates repositories
and commits/rolls back a single database transaction.  Service-layer
code uses the UoW to ensure that all writes within a business operation
are atomic.
"""

from __future__ import annotations

from typing import Self

from sqlalchemy.orm import Session

from .database import SessionLocal
from .repositories.answer import AnswerRepository
from .repositories.session import InterviewSessionRepository


class UnitOfWork:
    """Unit of Work — coordinates database operations in a single transaction.

    Usage::

        with UnitOfWork() as uow:
            session = uow.sessions.get(session_id)
            uow.sessions.complete_session(session)
            uow.commit()  # or rollback on exception

    Typical pattern (auto-commit)::

        with UnitOfWork(auto_commit=True) as uow:
            ...
    """

    def __init__(self, auto_commit: bool = False) -> None:
        """Initialize the Unit of Work.

        Args:
            auto_commit: If True, automatically calls ``commit()`` on exit
                if no exception occurred.
        """
        self._session: Session | None = None
        self._sessions_repo: InterviewSessionRepository | None = None
        self._answers_repo: AnswerRepository | None = None
        self._auto_commit = auto_commit

    # ------------------------------------------------------------------
    # Repository accessors (lazy-initialised)
    # ------------------------------------------------------------------

    @property
    def sessions(self) -> InterviewSessionRepository:
        """Access the ``InterviewSessionRepository`` bound to this UoW."""
        if self._sessions_repo is None:
            self._sessions_repo = InterviewSessionRepository(self.session)
        return self._sessions_repo

    @property
    def answers(self) -> AnswerRepository:
        """Access the ``AnswerRepository`` bound to this UoW."""
        if self._answers_repo is None:
            self._answers_repo = AnswerRepository(self.session)
        return self._answers_repo

    @property
    def session(self) -> Session:
        """Access the underlying SQLAlchemy ``Session``."""
        if self._session is None:
            self._session = SessionLocal()
        return self._session

    # ------------------------------------------------------------------
    # Transaction lifecycle
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """Commit the current transaction."""
        self.session.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self.session.rollback()

    def flush(self) -> None:
        """Flush pending changes to the database (no commit)."""
        self.session.flush()

    def close(self) -> None:
        """Release database resources."""
        if self._session is not None:
            self._session.close()

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            if exc_type is None and self._auto_commit:
                self.commit()
            elif exc_type is not None:
                self.rollback()
        finally:
            self.close()
