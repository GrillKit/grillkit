# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Unit of Work pattern for atomic database transactions.

Provides a base ``UnitOfWork`` context manager that owns a SQLAlchemy
session and transaction lifecycle. Feature modules extend it with their
own repository accessors (for example ``InterviewUnitOfWork``).
"""

from __future__ import annotations

from typing import Self

from sqlalchemy.orm import Session

from app.shared.infrastructure import database


class UnitOfWork:
    """Base unit of work — session and transaction lifecycle only.

    Usage::

        with UnitOfWork() as uow:
            ...
            uow.commit()

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
        self._auto_commit = auto_commit

    @property
    def session(self) -> Session:
        """Access the underlying SQLAlchemy ``Session``."""
        if self._session is None:
            self._session = database.SessionLocal()
        return self._session

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
