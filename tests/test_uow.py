# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Unit of Work pattern."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Answer, Interview
from app.shared.infrastructure.uow import UnitOfWork
from tests.helpers.selection import minimal_selection_spec


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

    Patches ``app.shared.infrastructure.database.SessionLocal`` so feature UoW
    classes use the test engine.
    """
    from app.shared.infrastructure import database as db_module

    maker = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(db_module, "SessionLocal", maker)


class TestUnitOfWork:
    """Tests for base and interview UnitOfWork context managers."""

    def test_commit_on_success(self, patch_session_local):
        """Test auto_commit=True commits on successful exit."""
        with InterviewUnitOfWork(auto_commit=True) as uow:
            session = Interview(
                id="uow-test-1", selection_spec=minimal_selection_spec()
            )
            uow.interviews.add(session)

        # Verify the session was committed by reading it back
        with InterviewUnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-1")
            assert loaded is not None
            assert loaded.id == "uow-test-1"

    def test_rollback_on_error(self, patch_session_local):
        """Test auto_commit=True rolls back on exception."""
        with (
            pytest.raises(ValueError, match="test error"),
            InterviewUnitOfWork(auto_commit=True) as uow,
        ):
            session = Interview(
                id="uow-test-2", selection_spec=minimal_selection_spec()
            )
            uow.interviews.add(session)
            raise ValueError("test error")

        # Verify the session was NOT committed
        with InterviewUnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-2")
            assert loaded is None

    def test_no_auto_commit(self, patch_session_local):
        """Test auto_commit=False does not commit automatically."""
        with InterviewUnitOfWork(auto_commit=False) as uow:
            session = Interview(
                id="uow-test-3", selection_spec=minimal_selection_spec()
            )
            uow.interviews.add(session)

        with InterviewUnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-3")
            assert loaded is None

    def test_manual_commit(self, patch_session_local):
        """Test manual commit() works."""
        with InterviewUnitOfWork(auto_commit=False) as uow:
            session = Interview(
                id="uow-test-4", selection_spec=minimal_selection_spec()
            )
            uow.interviews.add(session)
            uow.commit()

        with InterviewUnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-4")
            assert loaded is not None

    def test_manual_rollback(self, patch_session_local):
        """Test manual rollback() works."""
        with InterviewUnitOfWork(auto_commit=False) as uow:
            session = Interview(
                id="uow-test-5", selection_spec=minimal_selection_spec()
            )
            uow.interviews.add(session)
            uow.flush()
            uow.rollback()

        with InterviewUnitOfWork() as uow:
            loaded = uow.interviews.get("uow-test-5")
            assert loaded is None

    def test_interview_repository_accessor(self, patch_session_local):
        """Test that ``.interviews`` returns the interview repository type."""
        with InterviewUnitOfWork() as uow:
            from app.interview.repositories.interview import InterviewRepository

            assert isinstance(uow.interviews, InterviewRepository)

    def test_nested_answers_persist_with_interview(self, patch_session_local):
        """Answer rows added via ``Interview.answers`` are loaded with the session."""
        with InterviewUnitOfWork(auto_commit=True) as uow:
            interview = Interview(
                id="uow-test-6", selection_spec=minimal_selection_spec()
            )
            interview.answers = [
                Answer(
                    interview_id="uow-test-6",
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="What?",
                )
            ]
            uow.interviews.add(interview)

        with InterviewUnitOfWork() as uow:
            loaded_session = uow.interviews.get("uow-test-6")
            assert loaded_session is not None
            assert len(loaded_session.answers) == 1
            assert loaded_session.answers[0].question_id == "q1"

    def test_flush(self, patch_session_local):
        """Test flush() sends changes to DB without committing."""
        with InterviewUnitOfWork(auto_commit=False) as uow:
            session = Interview(
                id="uow-test-7", selection_spec=minimal_selection_spec()
            )
            uow.interviews.add(session)
            uow.flush()

            loaded = uow.interviews.get("uow-test-7")
            assert loaded is not None

        with InterviewUnitOfWork() as uow:
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
        """Test that the interview repository is created lazily."""
        uow = InterviewUnitOfWork()
        assert uow._interviews_repo is None
        _ = uow.interviews
        assert uow._interviews_repo is not None
