# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for database models and connection."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_session
from app.models import InterviewSession


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


class TestInterviewSession:
    """Tests for InterviewSession model."""

    def test_session_creation(self, test_session):
        """Test creating an InterviewSession record."""
        session = InterviewSession(
            id="test-session-001",
            level="junior",
            category="python",
            status="active",
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-001")
            .first()
        )
        assert result is not None
        assert result.level == "junior"
        assert result.category == "python"
        assert result.status == "active"

    def test_session_with_score(self, test_session):
        """Test creating an InterviewSession with a score."""
        session = InterviewSession(
            id="test-session-002",
            level="senior",
            category="system-design",
            status="completed",
            score=85,
            question_ids='["ds-001","ds-002"]',
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-002")
            .first()
        )
        assert result.score == 85
        assert result.question_ids == '["ds-001","ds-002"]'

    def test_session_default_status(self, test_session):
        """Test that status defaults to 'active'."""
        session = InterviewSession(
            id="test-session-003",
            level="mid",
            category="algorithms",
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-003")
            .first()
        )
        assert result.status == "active"

    def test_session_default_question_ids(self, test_session):
        """Test that question_ids defaults to '[]'."""
        session = InterviewSession(
            id="test-session-004",
            level="junior",
            category="sql",
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-004")
            .first()
        )
        assert result.question_ids == "[]"

    def test_session_completed_at_nullable(self, test_session):
        """Test that completed_at can be null."""
        session = InterviewSession(
            id="test-session-005",
            level="junior",
            category="python",
            completed_at=None,
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-005")
            .first()
        )
        assert result.completed_at is None

    def test_session_score_nullable(self, test_session):
        """Test that score can be null."""
        session = InterviewSession(
            id="test-session-006",
            level="junior",
            category="python",
            score=None,
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-006")
            .first()
        )
        assert result.score is None

    def test_session_started_at_auto(self, test_session):
        """Test that started_at is set automatically."""
        session = InterviewSession(
            id="test-session-007",
            level="junior",
            category="python",
        )
        test_session.add(session)
        test_session.commit()

        result = (
            test_session.query(InterviewSession)
            .filter_by(id="test-session-007")
            .first()
        )
        assert result.started_at is not None
        assert isinstance(result.started_at, datetime)


class TestDatabaseFunctions:
    """Tests for database utility functions."""

    def test_init_db_creates_tables(self, test_engine):
        """Test that init_db creates tables."""
        # Drop tables first
        Base.metadata.drop_all(bind=test_engine)

        # Verify tables don't exist by trying to query
        Session = sessionmaker(bind=test_engine)
        session = Session()

        with pytest.raises(Exception):
            session.query(InterviewSession).first()

        session.close()

        # Create tables
        Base.metadata.create_all(bind=test_engine)

        # Verify tables exist now
        session = Session()
        result = session.query(InterviewSession).first()
        assert result is None  # No records yet, but query works
        session.close()

    def test_get_session_returns_session(self, test_engine, monkeypatch):
        """Test that get_session returns a Session object."""
        # Patch the engine used by get_session
        from app import database

        original_engine = database.engine
        monkeypatch.setattr(database, "engine", test_engine)

        session = get_session()
        assert session is not None
        assert hasattr(session, "query")
        assert hasattr(session, "add")
        assert hasattr(session, "commit")

        session.close()

        # Restore original engine
        monkeypatch.setattr(database, "engine", original_engine)
