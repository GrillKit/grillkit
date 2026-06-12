# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository layer (base, session, answer)."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.value_objects import SessionSelection, TrackSelection
from app.interview.repositories.interview import InterviewRepository
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Answer, Interview
from app.shared.repositories.base import SqlAlchemyRepository
from tests.helpers.selection import minimal_selection_spec
from tests.helpers.theory_seed import attach_theory_section_to_answers


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine):
    """Create a test database session."""
    _Session = sessionmaker(bind=engine)  # noqa: N806
    session = _Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_test_interview(
    db_session,
    interview_id: str = "session-1",
    *,
    question_count: int = 3,
) -> Interview:
    sess = Interview(
        id=interview_id,
        selection_spec=minimal_selection_spec(),
        status="active",
    )
    db_session.add(sess)
    db_session.flush()
    attach_theory_section_to_answers(
        db_session,
        sess,
        [],
        question_count=question_count,
    )
    db_session.commit()
    return sess


def _create_test_answer(
    db_session,
    interview_id: str = "session-1",
    question_id: str = "q1",
    order: int = 1,
    round_num: int = 0,
    question_text: str = "What is Python?",
) -> Answer:
    interview = db_session.get(Interview, interview_id)
    assert interview is not None
    section = interview.theory_section
    assert section is not None
    ans = Answer(
        theory_section_id=section.id,
        question_id=question_id,
        order=order,
        round=round_num,
        question_text=question_text,
    )
    db_session.add(ans)
    db_session.commit()
    return ans


# ======================================================================
# SqlAlchemyRepository (base)
# ======================================================================


class _ConcreteRepo(SqlAlchemyRepository[Interview]):
    """Concrete subclass for testing the base repository."""

    _model = Interview


class TestSqlAlchemyRepository:
    """Tests for the generic SQLAlchemy repository base."""

    def test_add_and_get(self, db_session):
        """Test adding an entity and retrieving it by ID."""
        repo = _ConcreteRepo(db_session)
        session = Interview(id="test-1", selection_spec=minimal_selection_spec())
        repo.add(session)
        db_session.commit()

        result = repo.get("test-1")
        assert result is not None
        assert result.id == "test-1"
        assert result.selection_spec

    def test_get_not_found(self, db_session):
        """Test get returns None for missing entity."""
        repo = _ConcreteRepo(db_session)
        result = repo.get("non-existent")
        assert result is None

    def test_list_all_empty(self, db_session):
        """Test list_all returns empty list when no entities exist."""
        repo = _ConcreteRepo(db_session)
        results = repo.list_all()
        assert results == []

    def test_list_all(self, db_session):
        """Test list_all returns all entities."""
        repo = _ConcreteRepo(db_session)
        repo.add(Interview(id="a1", selection_spec=minimal_selection_spec()))
        repo.add(
            Interview(
                id="a2",
                selection_spec=minimal_selection_spec(
                    level="middle", categories=["ds"]
                ),
            )
        )
        db_session.commit()

        results = repo.list_all()
        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {"a1", "a2"}


# ======================================================================
# InterviewRepository
# ======================================================================


class TestInterviewRepository:
    """Tests for InterviewRepository shell persistence."""

    def test_get_eager_loads_theory_tasks(self, db_session):
        """Test get() eagerly loads theory section tasks."""
        _create_test_interview(db_session)
        _create_test_answer(db_session)

        repo = InterviewRepository(db_session)
        session = repo.get("session-1")
        assert session is not None
        assert session.theory_section is not None
        assert len(session.theory_section.tasks) == 1

    def test_save_aggregate_persists_completed_session(self, db_session):
        """save_aggregate writes completed status and overall feedback."""
        _create_test_interview(db_session, interview_id="session-1")
        _create_test_answer(db_session, question_id="q1", order=1)
        _create_test_answer(db_session, question_id="q2", order=2)

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        completed = aggregate.with_session_completed({"summary": "done"})
        repo.save_aggregate(completed)
        db_session.commit()

        reloaded = repo.get_aggregate("session-1")
        assert reloaded is not None
        assert reloaded.status == "completed"
        assert reloaded.completed_at is not None
        assert isinstance(reloaded.completed_at, datetime)
        assert reloaded.overall_feedback == {"summary": "done"}

    def test_get_not_found(self, db_session):
        """Test get returns None for missing ID."""
        repo = InterviewRepository(db_session)
        assert repo.get("nope") is None

    def test_create_shell_inserts_interview(self, db_session):
        """create_shell persists a new interview shell row."""
        selection = SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
            question_count=1,
            task_time_limit_seconds=60,
        )
        shell = DomainInterview.start_shell(
            "new-session",
            selection=selection,
            locale="en",
        )

        repo = InterviewRepository(db_session)
        persisted = repo.create_shell(shell)
        db_session.commit()

        assert persisted.id == "new-session"
        assert persisted.status == "active"
        reloaded = repo.get_aggregate("new-session")
        assert reloaded is not None
        assert reloaded.locale == "en"

    def test_get_aggregate_maps_domain_shell(self, db_session):
        """get_aggregate returns a domain interview shell without tasks."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q1", order=1)
        _create_test_answer(db_session, question_id="q2", order=2)

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")

        assert aggregate is not None
        assert aggregate.id == "session-1"
        assert aggregate.status == "active"

    def test_get_read_model_composes_theory_tasks(self, db_session):
        """get_read_model composes answers from the linked theory section."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q1", order=1)

        repo = InterviewRepository(db_session)
        read_model = repo.get_read_model("session-1")

        assert read_model is not None
        assert read_model.question_count == 3
        assert len(read_model.answers) == 1
        assert read_model.answers[0].question_id == "q1"
