# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for dashboard interview history queries."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.interview.domain.serialization import session_to_spec
from app.interview.domain.value_objects import (
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.mappers import interview_read_from_orm
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.dashboard import DashboardRowRead
from app.interview.schemas.interview import InterviewRead
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.read_model import load_recent_interview_reads
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Interview
from tests.helpers.selection import minimal_selection_spec
from tests.helpers.theory_seed import create_theory_section_for_interview


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
    result = DashboardBuilder.format_local_datetime(dt)
    assert "2026" in result
    assert ":" in result


def test_interview_display_title():
    """Title is built from selection_spec."""
    interview = Interview(
        id="x",
        selection_spec=minimal_selection_spec(categories=["data-structures"]),
    )
    read_model = interview_read_from_orm(interview)
    assert DashboardBuilder.interview_display_title(read_model) == "Python Interview"


def test_interview_display_title_coding_only():
    """Coding-only sessions use coding sources for the dashboard title."""
    spec = session_to_spec(
        SessionSelection(
            session_mode="coding_only",
            theory=SectionBranchSpec(
                enabled=False,
                question_count=0,
                task_time_limit_seconds=None,
                sources=(),
            ),
            coding=SectionBranchSpec(
                enabled=True,
                question_count=1,
                task_time_limit_seconds=None,
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("basics",),
                    ),
                ),
            ),
        )
    )
    interview = Interview(id="coding-1", selection_spec=spec)
    read_model = interview_read_from_orm(interview)
    assert DashboardBuilder.interview_display_title(read_model) == "Python Interview"


def test_list_recent_ordering(db_session):
    """load_recent_interview_reads returns completed before older active when newer."""
    now = datetime.now(UTC)
    active = Interview(
        id="active-1",
        selection_spec=minimal_selection_spec(categories=["basics"]),
        status="active",
        started_at=now - timedelta(hours=2),
    )
    completed = Interview(
        id="done-1",
        selection_spec=minimal_selection_spec(categories=["algorithms"]),
        status="completed",
        started_at=now - timedelta(hours=3),
        completed_at=now,
    )
    db_session.add(active)
    db_session.add(completed)
    db_session.flush()
    create_theory_section_for_interview(
        db_session,
        active,
        question_count=5,
    )
    create_theory_section_for_interview(
        db_session,
        completed,
        question_count=3,
    )
    db_session.commit()

    class TestUow(InterviewUnitOfWork):
        def __init__(self) -> None:
            super().__init__()
            self._session = db_session

    with TestUow() as uow:
        recent = load_recent_interview_reads(uow, limit=20)
    assert [i.id for i in recent] == ["done-1", "active-1"]


def test_compute_max_score_uses_nested_breakdown_for_coding_only():
    """Coding-only completed sessions read max score from nested breakdown."""
    interview = InterviewRead(
        id="coding-done",
        status="completed",
        locale="en",
        selection_spec=minimal_selection_spec(categories=["basics"]),
        question_ids="[]",
        question_count=0,
        question_time_limit_seconds=None,
        answers=[],
        score=4,
        overall_feedback={
            "score_breakdown": {
                "coding": {
                    "score": 4,
                    "max": 5,
                    "skipped": False,
                    "questions": {"cod-001": {"score": 4, "max": 5}},
                }
            }
        },
    )
    assert (
        DashboardBuilder.compute_max_score(
            interview,
            interview.overall_feedback["score_breakdown"],
        )
        == 5
    )


def test_list_dashboard_rows(monkeypatch):
    """Dashboard rows map interview fields for the template."""
    now = datetime.now(UTC)
    completed = InterviewRead(
        id="done-1",
        status="completed",
        locale="en",
        selection_spec=minimal_selection_spec(categories=["algorithms"]),
        question_ids='["q1"]',
        question_count=3,
        question_time_limit_seconds=None,
        answers=[],
        score=8,
        overall_feedback={
            "score_breakdown": {
                "theory": {"score": 8, "max": 15, "skipped": False},
            }
        },
        completed_at=now,
    )
    active = InterviewRead(
        id="active-1",
        status="active",
        locale="en",
        selection_spec=minimal_selection_spec(categories=["basics"]),
        question_ids='["q1"]',
        question_count=5,
        question_time_limit_seconds=None,
        answers=[],
        started_at=now,
    )

    monkeypatch.setattr(
        "app.interview.services.dashboard.load_recent_interview_reads",
        lambda uow, limit=20: [completed, active],
    )

    class _FakeCodingSections:
        @staticmethod
        def get_aggregates_by_interview_ids(interview_ids):
            del interview_ids
            return {}

    class _FakeUow:
        coding_sections = _FakeCodingSections()

    rows = DashboardBuilder(_FakeUow()).list_rows(limit=20)  # type: ignore[arg-type]
    assert len(rows) == 2
    assert rows[0].title == "Python Interview"
    assert rows[0].session_mode_label == "Theory"
    assert rows[0].score_display == "8 / 15"
    assert rows[0].status_label == "Completed"
    assert rows[1].score_display == "—"
    assert rows[1].status_label == "Active"
    assert rows[0].url == "/interview/done-1/results"
    assert isinstance(rows[0], DashboardRowRead)
