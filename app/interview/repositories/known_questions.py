# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Repository for known bank-item exclusions."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.interview.domain.value_objects import SectionKind
from app.shared.infrastructure.models import KnownQuestion
from app.shared.repositories.base import SqlAlchemyRepository


class KnownQuestionsRepository(SqlAlchemyRepository[KnownQuestion]):
    """Repository for ``known_questions`` rows.

    Attributes:
        _session: Active SQLAlchemy Session (inherited).
    """

    _model = KnownQuestion

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        super().__init__(session)

    def list_ids(self, branch: SectionKind) -> frozenset[str]:
        """Return bank item IDs marked as known for a branch.

        Args:
            branch: ``theory`` or ``coding``.

        Returns:
            Frozenset of excluded bank item IDs.
        """
        rows = self._session.scalars(
            select(KnownQuestion.bank_item_id).where(KnownQuestion.branch == branch)
        ).all()
        return frozenset(rows)

    def list_all_grouped(self) -> dict[str, list[str]]:
        """Return all known bank item IDs grouped by branch.

        Returns:
            Dict with ``theory`` and ``coding`` keys mapping to sorted ID lists.
        """
        rows = self._session.scalars(
            select(KnownQuestion).order_by(
                KnownQuestion.branch, KnownQuestion.bank_item_id
            )
        ).all()
        grouped: dict[str, list[str]] = {"theory": [], "coding": []}
        for row in rows:
            grouped.setdefault(row.branch, []).append(row.bank_item_id)
        return grouped

    def count(self) -> int:
        """Return total number of known bank item rows.

        Returns:
            Row count across both branches.
        """
        return (
            self._session.scalar(select(func.count()).select_from(KnownQuestion)) or 0
        )

    def mark(self, branch: SectionKind, bank_item_id: str) -> None:
        """Insert a known bank item row if it does not exist.

        Args:
            branch: ``theory`` or ``coding``.
            bank_item_id: ID from the YAML bank for that branch.
        """
        existing = self._session.scalar(
            select(KnownQuestion).where(
                KnownQuestion.branch == branch,
                KnownQuestion.bank_item_id == bank_item_id,
            )
        )
        if existing is None:
            self._session.add(KnownQuestion(branch=branch, bank_item_id=bank_item_id))
            self._session.flush()

    def unmark(self, branch: SectionKind, bank_item_id: str) -> None:
        """Remove a known bank item row if present.

        Args:
            branch: ``theory`` or ``coding``.
            bank_item_id: ID from the YAML bank for that branch.
        """
        self._session.execute(
            delete(KnownQuestion).where(
                KnownQuestion.branch == branch,
                KnownQuestion.bank_item_id == bank_item_id,
            )
        )
