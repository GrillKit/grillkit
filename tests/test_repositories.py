# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository layer (base, session, answer)."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.interview.domain.entities import Answer as DomainAnswer
from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.value_objects import (
    InterviewSelection,
    PlannedQuestion,
    TrackSelection,
)
from app.interview.repositories.interview import InterviewRepository
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Answer, Interview
from app.shared.repositories.base import SqlAlchemyRepository
from tests.helpers.selection import minimal_selection_spec


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


def _create_test_interview(db_session, interview_id="session-1") -> Interview:
    sess = Interview(
        id=interview_id,
        selection_spec=minimal_selection_spec(),
        question_count=3,
        question_ids='["q1","q2","q3"]',
        status="active",
    )
    db_session.add(sess)
    db_session.commit()
    return sess


def _create_test_answer(
    db_session,
    interview_id="session-1",
    question_id="q1",
    order=1,
    round_num=0,
    question_text="What is Python?",
) -> Answer:
    ans = Answer(
        interview_id=interview_id,
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
    """Tests for InterviewRepository."""

    def test_get_eager_loads_answers(self, db_session):
        """Test get() eagerly loads the answers relationship."""
        _create_test_interview(db_session)
        _create_test_answer(db_session)

        repo = InterviewRepository(db_session)
        session = repo.get("session-1")
        assert session is not None
        # answers should be loaded (no lazy-load error)
        assert len(session.answers) == 1

    def test_save_aggregate_persists_completed_session(self, db_session):
        """save_aggregate writes completed status, score, and overall feedback."""
        _create_test_interview(db_session, interview_id="session-1")
        a1 = _create_test_answer(db_session, question_id="q1", order=1)
        a1.answer_text = "a"
        a1.score = 4
        a2 = _create_test_answer(db_session, question_id="q2", order=2)
        a2.answer_text = "b"
        a2.score = 3
        db_session.commit()

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        completed = aggregate.with_session_completed({"summary": "done"})
        repo.save_aggregate(completed)
        db_session.commit()

        reloaded = repo.get_aggregate("session-1")
        assert reloaded is not None
        assert reloaded.status == "completed"
        assert reloaded.score == 7
        assert reloaded.completed_at is not None
        assert isinstance(reloaded.completed_at, datetime)
        assert reloaded.overall_feedback == {"summary": "done"}

    def test_get_not_found(self, db_session):
        """Test get returns None for missing ID."""
        repo = InterviewRepository(db_session)
        assert repo.get("nope") is None

    def test_create_aggregate_inserts_interview_and_answers(self, db_session):
        """create_aggregate persists a new domain aggregate with real answer IDs."""
        selection = InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        )
        planned = (
            PlannedQuestion(
                id="q1",
                text="Question one",
                code=None,
            ),
        )
        aggregate = DomainInterview.start(
            "new-session",
            selection=selection,
            locale="en",
            planned_questions=planned,
            question_time_limit_seconds=60,
        )

        repo = InterviewRepository(db_session)
        persisted = repo.create_aggregate(aggregate)
        db_session.commit()

        assert persisted.id == "new-session"
        assert persisted.question_count == 1
        assert persisted.answers[0].id != DomainAnswer.NEW_ID
        assert persisted.answers[0].started_at is not None
        reloaded = repo.get_aggregate("new-session")
        assert reloaded is not None
        assert reloaded.answers[0].question_text == "Question one"

    def test_get_aggregate_maps_domain_interview(self, db_session):
        """get_aggregate returns a domain interview with answers."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q1", order=1)
        _create_test_answer(db_session, question_id="q2", order=2)

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")

        assert aggregate is not None
        assert aggregate.id == "session-1"
        assert aggregate.status == "active"
        assert len(aggregate.answers) == 2
        assert aggregate.answers[0].question_id == "q1"

    def test_save_aggregate_persists_answer_started_at(self, db_session):
        """save_aggregate writes answer timer state from the domain model."""
        interview = _create_test_interview(db_session, interview_id="session-1")
        interview.question_time_limit_seconds = 120
        db_session.commit()
        a1 = _create_test_answer(db_session, question_id="q1", order=1)
        _create_test_answer(db_session, question_id="q2", order=2)

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        updated = aggregate.start_timer_for_answer(a1.id)
        repo.save_aggregate(updated)
        db_session.commit()

        reloaded = repo.get("session-1")
        assert reloaded is not None
        started = next(ans for ans in reloaded.answers if ans.id == a1.id)
        assert started.started_at is not None

    def test_save_aggregate_persists_answer_text(self, db_session):
        """save_aggregate writes answer_text from the domain model."""
        _create_test_interview(db_session, interview_id="session-1")
        a1 = _create_test_answer(db_session, question_id="q1", order=1)

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        updated = aggregate.with_answer_text(a1.id, "Lists are mutable.")
        repo.save_aggregate(updated)
        db_session.commit()

        reloaded = repo.get_aggregate("session-1")
        assert reloaded is not None
        saved = next(ans for ans in reloaded.answers if ans.id == a1.id)
        assert saved.answer_text == "Lists are mutable."

    def test_save_aggregate_persists_timed_out_round(self, db_session):
        """save_aggregate writes timeout marker, score, and feedback."""
        _create_test_interview(db_session, interview_id="session-1")
        a1 = _create_test_answer(db_session, question_id="q1", order=1)

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        updated = aggregate.with_timed_out_round(a1.id, "Time expired.")
        repo.save_aggregate(updated)
        db_session.commit()

        reloaded = repo.get_aggregate("session-1")
        assert reloaded is not None
        saved = next(ans for ans in reloaded.answers if ans.id == a1.id)
        assert saved.answer_text == DomainAnswer.TIME_EXPIRED_ANSWER_TEXT
        assert saved.score == 0
        assert saved.feedback

    def test_save_aggregate_persists_evaluation(self, db_session):
        """save_aggregate writes AI score and feedback from the domain model."""
        _create_test_interview(db_session, interview_id="session-1")
        a1 = _create_test_answer(db_session, question_id="q1", order=1)
        a1.answer_text = "my answer"
        db_session.commit()

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        updated = aggregate.with_evaluation("q1", 0, 5, "Excellent.")
        repo.save_aggregate(updated)
        db_session.commit()

        reloaded = repo.get_aggregate("session-1")
        assert reloaded is not None
        saved = reloaded.find_answer("q1", 0)
        assert saved.score == 5
        assert saved.feedback == "Excellent."

    def test_save_aggregate_inserts_follow_up(self, db_session):
        """save_aggregate inserts a new follow-up answer row."""
        _create_test_interview(db_session, interview_id="session-1")
        a1 = _create_test_answer(db_session, question_id="q1", order=1)
        a1.answer_text = "done"
        a1.score = 4
        db_session.commit()

        repo = InterviewRepository(db_session)
        aggregate = repo.get_aggregate("session-1")
        assert aggregate is not None
        evaluated = aggregate.with_evaluation("q1", 0, 4, "Good.")
        updated, _ = evaluated.with_follow_up("q1", "Tell me more.")
        repo.save_aggregate(updated)
        db_session.commit()

        reloaded = repo.get_aggregate("session-1")
        assert reloaded is not None
        assert len(reloaded.answers) == 2
        follow_up = reloaded.find_answer("q1", 1)
        assert follow_up.id != DomainAnswer.NEW_ID
        assert follow_up.question_text == "Tell me more."
        assert follow_up.answer_text is None
