# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for known questions repository."""

from app.interview.repositories.known_questions import KnownQuestionsRepository
from app.interview.repositories.uow import InterviewUnitOfWork


def test_mark_and_list_ids(isolated_db) -> None:
    """Marking a question stores it for the matching branch."""
    del isolated_db
    with InterviewUnitOfWork() as uow:
        repo = KnownQuestionsRepository(uow.session)
        repo.mark("theory", "bas-001")
        uow.commit()
        assert repo.list_ids("theory") == frozenset({"bas-001"})
        assert repo.list_ids("coding") == frozenset()


def test_mark_is_idempotent(isolated_db) -> None:
    """Repeated marks do not create duplicate rows."""
    del isolated_db
    with InterviewUnitOfWork() as uow:
        repo = KnownQuestionsRepository(uow.session)
        repo.mark("theory", "bas-001")
        repo.mark("theory", "bas-001")
        uow.commit()
        assert repo.count() == 1


def test_unmark_is_idempotent(isolated_db) -> None:
    """Unmarking a missing row succeeds without error."""
    del isolated_db
    with InterviewUnitOfWork() as uow:
        repo = KnownQuestionsRepository(uow.session)
        repo.unmark("theory", "missing")
        uow.commit()
        assert repo.list_ids("theory") == frozenset()


def test_list_all_grouped(isolated_db) -> None:
    """list_all_grouped returns sorted IDs per branch."""
    del isolated_db
    with InterviewUnitOfWork() as uow:
        repo = KnownQuestionsRepository(uow.session)
        repo.mark("theory", "bas-002")
        repo.mark("theory", "bas-001")
        repo.mark("coding", "algo-001")
        uow.commit()
        grouped = repo.list_all_grouped()
        assert grouped["theory"] == ["bas-001", "bas-002"]
        assert grouped["coding"] == ["algo-001"]
        assert repo.count() == 3
