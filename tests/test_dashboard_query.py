# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for dashboard interview history queries."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Interview
from app.repositories.interview import InterviewRepository
from app.services.interview_query import DashboardInterviewRow, InterviewQuery


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def db_session(engine):
    """Create a test database session."""
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_format_local_datetime_utc():
    """UTC datetimes are converted to local formatted strings."""
    dt = datetime(2026, 5, 18, 12, 30, tzinfo=UTC)
    result = InterviewQuery.format_local_datetime(dt)
    assert "2026" in result
    assert ":" in result


def test_interview_display_title():
    """Title is built from language field."""
    interview = Interview(
        id="x",
        level="junior",
        language="python",
        category="data-structures",
    )
    assert InterviewQuery.interview_display_title(interview) == "Python Interview"


def test_list_recent_ordering(db_session):
    """list_recent returns completed before older active when completed is newer."""
    now = datetime.now(UTC)
    active = Interview(
        id="active-1",
        level="junior",
        language="python",
        category="basics",
        question_count=5,
        status="active",
        started_at=now - timedelta(hours=2),
    )
    completed = Interview(
        id="done-1",
        level="junior",
        language="python",
        category="algorithms",
        question_count=3,
        status="completed",
        score=10,
        started_at=now - timedelta(hours=3),
        completed_at=now,
    )
    db_session.add(active)
    db_session.add(completed)
    db_session.commit()

    repo = InterviewRepository(db_session)
    recent = repo.list_recent(limit=20)
    assert [i.id for i in recent] == ["done-1", "active-1"]


def test_list_dashboard_rows(monkeypatch):
    """Dashboard rows map interview fields for the template."""
    now = datetime.now(UTC)
    completed = Interview(
        id="done-1",
        level="junior",
        language="python",
        category="algorithms",
        question_count=3,
        status="completed",
        score=8,
        completed_at=now,
    )
    completed.answers = []
    active = Interview(
        id="active-1",
        level="junior",
        language="python",
        category="basics",
        question_count=5,
        status="active",
        started_at=now,
    )
    active.answers = []

    class FakeInterviews:
        @staticmethod
        def list_recent(limit=20):
            return [completed, active]

    class FakeUow:
        def __init__(self, auto_commit=False):
            self.interviews = FakeInterviews()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.services.interview_query.UnitOfWork",
        FakeUow,
    )

    rows = InterviewQuery.list_dashboard_rows(limit=20)
    assert len(rows) == 2
    assert rows[0].title == "Python Interview"
    assert rows[0].score_display == "8 / 0"
    assert rows[0].status_label == "Completed"
    assert rows[1].score_display == "—"
    assert rows[1].status_label == "Active"
    assert rows[0].url == "/interview/done-1"
    assert isinstance(rows[0], DashboardInterviewRow)
