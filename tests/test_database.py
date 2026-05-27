# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for database models and connection."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Interview
from tests.helpers.selection import minimal_selection_spec


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
    _Session = sessionmaker(bind=test_engine)  # noqa: N806
    session = _Session()
    yield session
    session.close()


class TestInterview:
    """Tests for Interview model."""

    def test_interview_creation(self, test_session):
        """Test creating an Interview record."""
        spec = minimal_selection_spec()
        session = Interview(
            id="test-session-001",
            selection_spec=spec,
            status="active",
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-001").first()
        assert result is not None
        assert result.selection_spec == spec
        assert result.status == "active"

    def test_session_with_score(self, test_session):
        """Test creating an Interview with a score."""
        session = Interview(
            id="test-session-002",
            selection_spec=minimal_selection_spec(
                level="senior", categories=["system-design"]
            ),
            status="completed",
            score=85,
            question_ids='["ds-001","ds-002"]',
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-002").first()
        assert result.score == 85
        assert result.question_ids == '["ds-001","ds-002"]'

    def test_session_default_status(self, test_session):
        """Test that status defaults to 'active'."""
        session = Interview(
            id="test-session-003",
            selection_spec=minimal_selection_spec(categories=["algorithms"]),
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-003").first()
        assert result.status == "active"

    def test_session_default_question_ids(self, test_session):
        """Test that question_ids defaults to '[]'."""
        session = Interview(
            id="test-session-004",
            selection_spec=minimal_selection_spec(categories=["sql"]),
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-004").first()
        assert result.question_ids == "[]"

    def test_interview_completed_at_nullable(self, test_session):
        """Test that completed_at can be null."""
        session = Interview(
            id="test-session-005",
            selection_spec=minimal_selection_spec(),
            completed_at=None,
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-005").first()
        assert result.completed_at is None

    def test_session_score_nullable(self, test_session):
        """Test that score can be null."""
        session = Interview(
            id="test-session-006",
            selection_spec=minimal_selection_spec(),
            score=None,
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-006").first()
        assert result.score is None

    def test_session_started_at_auto(self, test_session):
        """Test that started_at is set automatically."""
        session = Interview(
            id="test-session-007",
            selection_spec=minimal_selection_spec(),
        )
        test_session.add(session)
        test_session.commit()

        result = test_session.query(Interview).filter_by(id="test-session-007").first()
        assert result.started_at is not None
        assert isinstance(result.started_at, datetime)


class TestDatabaseFunctions:
    """Tests for database utility functions."""

    def test_create_all_creates_tables(self, test_engine):
        """Test that metadata.create_all creates tables."""
        Base.metadata.drop_all(bind=test_engine)

        _Session = sessionmaker(bind=test_engine)  # noqa: N806
        session = _Session()

        with pytest.raises(OperationalError):
            session.query(Interview).first()

        session.close()

        Base.metadata.create_all(bind=test_engine)

        session = _Session()
        result = session.query(Interview).first()
        assert result is None
        session.close()
