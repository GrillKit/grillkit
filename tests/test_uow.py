# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Unit of Work pattern."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Answer, Interview
from app.shared.infrastructure.uow import UnitOfWork


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def patch_session_local(engine, monkeypatch):
    """Monkeypatch SessionLocal to use the in-memory engine.

    Patches both ``app.shared.infrastructure.database.SessionLocal`` (the canonical source)
    and ``app.shared.infrastructure.uow.SessionLocal`` (the import-time copy) so that
    ``UnitOfWork`` uses the test engine.
    """
    from app.shared.infrastructure import database as db_module
    from app.shared.infrastructure import uow as uow_module

    maker = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(db_module, "SessionLocal", maker)
    monkeypatch.setattr(uow_module, "SessionLocal", maker)


class TestUnitOfWork:
    """Tests for UnitOfWork context manager."""

    def test_commit_on_success(self, patch_session_local):
        """Test auto_commit=True commits on successful exit."""
        with UnitOfWork(auto_commit=True) as uow:
            session = Interview(id="uow-test-1", level="junior", category="python")
            uow.interviews.add(session)

        # Verify the session was committed by reading it back
        with UnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-1")
            assert loaded is not None
            assert loaded.id == "uow-test-1"

    def test_rollback_on_error(self, patch_session_local):
        """Test auto_commit=True rolls back on exception."""
        with (
            pytest.raises(ValueError, match="test error"),
            UnitOfWork(auto_commit=True) as uow,
        ):
            session = Interview(id="uow-test-2", level="junior", category="python")
            uow.interviews.add(session)
            raise ValueError("test error")

        # Verify the session was NOT committed
        with UnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-2")
            assert loaded is None

    def test_no_auto_commit(self, patch_session_local):
        """Test auto_commit=False does not commit automatically."""
        with UnitOfWork(auto_commit=False) as uow:
            session = Interview(id="uow-test-3", level="junior", category="python")
            uow.interviews.add(session)
            # No commit called

        with UnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-3")
            assert loaded is None

    def test_manual_commit(self, patch_session_local):
        """Test manual commit() works."""
        with UnitOfWork(auto_commit=False) as uow:
            session = Interview(id="uow-test-4", level="junior", category="python")
            uow.interviews.add(session)
            uow.commit()

        with UnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-4")
            assert loaded is not None

    def test_manual_rollback(self, patch_session_local):
        """Test manual rollback() works."""
        with UnitOfWork(auto_commit=False) as uow:
            session = Interview(id="uow-test-5", level="junior", category="python")
            uow.interviews.add(session)
            uow.flush()  # ensure it's in the session
            uow.rollback()

        with UnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-5")
            assert loaded is None

    def test_repository_accessors(self, patch_session_local):
        """Test that .sessions and .answers return the correct repository types."""
        with UnitOfWork() as uow:
            from app.interview.repositories.answer import AnswerRepository
            from app.interview.repositories.interview import InterviewRepository

            assert isinstance(uow.interviews, InterviewRepository)
            assert isinstance(uow.answers, AnswerRepository)

    def test_repositories_share_same_session(self, patch_session_local):
        """Test that .sessions and .answers use the same underlying DB session."""
        with UnitOfWork(auto_commit=True) as uow:
            session = Interview(id="uow-test-6", level="junior", category="python")
            uow.interviews.add(session)

            answer = Answer(
                interview_id="uow-test-6",
                question_id="q1",
                order=1,
                round=0,
                question_text="What?",
            )
            uow.answers.add(answer)

        # Both should be visible in a single read
        with UnitOfWork() as uow:
            loaded_session = uow.interviews.get("uow-test-6")
            assert loaded_session is not None
            loaded_answer = uow.answers.get_by_interview_question_round(
                "uow-test-6", "q1", 0
            )
            assert loaded_answer is not None

    def test_flush(self, patch_session_local):
        """Test flush() sends changes to DB without committing."""
        with UnitOfWork(auto_commit=False) as uow:
            session = Interview(id="uow-test-7", level="junior", category="python")
            uow.interviews.add(session)
            uow.flush()

            # After flush, the session should be visible in the same UoW
            loaded = uow.interviews.get("uow-test-7")
            assert loaded is not None

        # But not committed
        with UnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-7")
            assert loaded is None

    def test_close_releases_resources(self, patch_session_local):
        """Test close() does not raise and releases the underlying session."""
        uow = UnitOfWork()
        session = uow.session  # trigger lazy init
        assert session is not None
        # close() should not raise
        uow.close()

    def test_lazy_session_initialization(self, patch_session_local):
        """Test that the DB session is created lazily."""
        uow = UnitOfWork()
        assert uow._session is None  # not yet created
        _ = uow.session  # trigger creation
        assert uow._session is not None

    def test_lazy_repository_initialization(self, patch_session_local):
        """Test that repositories are created lazily."""
        uow = UnitOfWork()
        assert uow._interviews_repo is None
        assert uow._answers_repo is None
        _ = uow.interviews  # trigger creation
        assert uow._interviews_repo is not None
        assert uow._answers_repo is None  # still lazy
