# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for known questions service."""

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.known_questions import KnownQuestionsService


def test_mark_unmark_and_list(isolated_db) -> None:
    """Service delegates mark, unmark, and list to the repository."""
    del isolated_db
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = KnownQuestionsService(uow)
        service.mark_known("theory", "bas-001")
        assert service.list_ids("theory") == frozenset({"bas-001"})
        assert service.count() == 1
        service.unmark("theory", "bas-001")
        assert service.list_ids("theory") == frozenset()
        assert service.list_all() == {"theory": [], "coding": []}
