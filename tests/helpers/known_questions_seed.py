# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding known questions directly via service."""

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.known_questions import KnownQuestionsService


def seed_known_question(branch: str, item_id: str) -> None:
    """Persist a known-question entry directly via the service.

    Args:
        branch: Either ``theory`` or ``coding``.
        item_id: YAML bank item identifier.
    """
    with InterviewUnitOfWork(auto_commit=True) as uow:
        KnownQuestionsService(uow).mark_known(branch, item_id)
