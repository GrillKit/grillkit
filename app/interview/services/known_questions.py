# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Service for managing known bank-item exclusions."""

from __future__ import annotations

from app.interview.domain.value_objects import SectionKind
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.bank_text import KnownQuestionView, resolve_known_views


class KnownQuestionsService:
    """Read and update the instance-wide known bank items list.

    Attributes:
        _uow: Application unit of work for persistence.
    """

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    def list_ids(self, branch: SectionKind) -> frozenset[str]:
        """Return bank item IDs marked as known for a branch.

        Args:
            branch: ``theory`` or ``coding``.

        Returns:
            Frozenset of excluded bank item IDs.
        """
        return self._uow.known_questions.list_ids(branch)

    def mark_known(self, branch: SectionKind, item_id: str) -> None:
        """Mark a bank item as known for future session exclusion.

        Args:
            branch: ``theory`` or ``coding``.
            item_id: ID from the YAML bank for that branch.
        """
        self._uow.known_questions.mark(branch, item_id)

    def unmark(self, branch: SectionKind, item_id: str) -> None:
        """Remove a bank item from the known list.

        Args:
            branch: ``theory`` or ``coding``.
            item_id: ID from the YAML bank for that branch.
        """
        self._uow.known_questions.unmark(branch, item_id)

    def list_all(self) -> dict[str, list[str]]:
        """Return all known bank item IDs grouped by branch.

        Returns:
            Dict with ``theory`` and ``coding`` keys mapping to ID lists.
        """
        return self._uow.known_questions.list_all_grouped()

    def list_all_with_text(self) -> dict[str, list[KnownQuestionView]]:
        """Return all known bank items grouped by branch, enriched with text.

        Returns:
            Dict with ``theory`` and ``coding`` keys mapping to display rows
            that pair each bank item ID with its resolved question text.
        """
        return resolve_known_views(self._uow.known_questions.list_all_grouped())

    def count(self) -> int:
        """Return total number of known bank item rows.

        Returns:
            Row count across both branches.
        """
        return self._uow.known_questions.count()
