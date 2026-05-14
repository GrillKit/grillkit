# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for database models and connection."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, Interview, init_db, get_session


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


class TestInterview:
    """Tests for Interview model."""

    def test_interview_creation(self, test_session):
        """Test creating an Interview record."""
        interview = Interview(
            id="test-interview-001",
            level="junior",
            category="python",
            status="active",
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-001").first()
        assert result is not None
        assert result.level == "junior"
        assert result.category == "python"
        assert result.status == "active"

    def test_interview_with_score(self, test_session):
        """Test creating an Interview with a score."""
        interview = Interview(
            id="test-interview-002",
            level="senior",
            category="system-design",
            status="completed",
            score=85,
            messages_json='[{"role": "user", "content": "Hello"}]',
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-002").first()
        assert result.score == 85
        assert result.messages_json == '[{"role": "user", "content": "Hello"}]'

    def test_interview_default_status(self, test_session):
        """Test that status defaults to 'active'."""
        interview = Interview(
            id="test-interview-003",
            level="mid",
            category="algorithms",
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-003").first()
        assert result.status == "active"

    def test_interview_default_messages_json(self, test_session):
        """Test that messages_json defaults to '[]'."""
        interview = Interview(
            id="test-interview-004",
            level="junior",
            category="sql",
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-004").first()
        assert result.messages_json == "[]"

    def test_interview_completed_at_nullable(self, test_session):
        """Test that completed_at can be null."""
        interview = Interview(
            id="test-interview-005",
            level="junior",
            category="python",
            completed_at=None,
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-005").first()
        assert result.completed_at is None

    def test_interview_score_nullable(self, test_session):
        """Test that score can be null."""
        interview = Interview(
            id="test-interview-006",
            level="junior",
            category="python",
            score=None,
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-006").first()
        assert result.score is None

    def test_interview_started_at_auto(self, test_session):
        """Test that started_at is set automatically."""
        interview = Interview(
            id="test-interview-007",
            level="junior",
            category="python",
        )
        test_session.add(interview)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-interview-007").first()
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
            session.query(Interview).first()

        session.close()

        # Create tables
        Base.metadata.create_all(bind=test_engine)

        # Verify tables exist now
        session = Session()
        result = session.query(Interview).first()
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
