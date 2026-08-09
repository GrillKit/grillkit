# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding known questions directly via service."""

from app.interview.repositories.known_questions import KnownQuestionsRepository
from app.interview.repositories.uow import InterviewUnitOfWork


def seed_known_question(branch: str, item_id: str) -> None:
    """Persist a known-question entry directly via the repository.

    Args:
        branch: Either ``theory`` or ``coding``.
        item_id: YAML bank item identifier.
    """
    with InterviewUnitOfWork(auto_commit=True) as uow:
        KnownQuestionsRepository(uow.session).mark(branch, item_id)
