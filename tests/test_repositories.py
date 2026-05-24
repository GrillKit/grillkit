# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository layer (base, session, answer)."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.interview.repositories.answer import AnswerRepository
from app.interview.repositories.interview import InterviewRepository
from app.shared.domain.exceptions import AnswerNotFoundError
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

    def test_mark_completed(self, db_session):
        """Test mark_completed() sets status, score, and timestamp."""
        _create_test_interview(db_session)
        a1 = _create_test_answer(db_session, question_id="q1")
        a1.score = 4
        a2 = _create_test_answer(db_session, question_id="q2")
        a2.score = 3
        db_session.commit()

        repo = InterviewRepository(db_session)
        session = repo.get("session-1")

        repo.mark_completed(session, score=7)

        assert session.status == "completed"
        assert session.score == 7
        assert session.completed_at is not None
        assert isinstance(session.completed_at, datetime)

    def test_mark_completed_zero_score(self, db_session):
        """Test mark_completed with zero score."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q1")

        repo = InterviewRepository(db_session)
        session = repo.get("session-1")

        repo.mark_completed(session, score=0)
        assert session.score == 0
        assert session.status == "completed"

    def test_save_evaluation_feedback(self, db_session):
        """Test save_evaluation_feedback() sets overall_feedback."""
        _create_test_interview(db_session)
        repo = InterviewRepository(db_session)
        session = repo.get("session-1")

        repo.save_evaluation_feedback(session, '{"score": 42}')
        assert session.overall_feedback == '{"score": 42}'

    def test_get_not_found(self, db_session):
        """Test get returns None for missing ID."""
        repo = InterviewRepository(db_session)
        assert repo.get("nope") is None


# ======================================================================
# AnswerRepository
# ======================================================================


class TestAnswerRepository:
    """Tests for AnswerRepository."""

    def test_get_by_interview_question_round(self, db_session):
        """Test finding an answer by session, question, and round."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q1", round_num=0)
        _create_test_answer(db_session, question_id="q1", round_num=1)

        repo = AnswerRepository(db_session)
        ans0 = repo.get_by_interview_question_round("session-1", "q1", 0)
        ans1 = repo.get_by_interview_question_round("session-1", "q1", 1)

        assert ans0.round == 0
        assert ans1.round == 1

    def test_get_by_interview_question_round_not_found(self, db_session):
        """Test raises when no answer matches."""
        repo = AnswerRepository(db_session)
        with pytest.raises(AnswerNotFoundError, match="Answer not found"):
            repo.get_by_interview_question_round("s1", "q99", 0)

    def test_get_max_round(self, db_session):
        """Test get_max_round returns highest round number."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q1", round_num=0)
        _create_test_answer(db_session, question_id="q1", round_num=1)
        _create_test_answer(db_session, question_id="q1", round_num=3)

        repo = AnswerRepository(db_session)
        assert repo.get_max_round("session-1", "q1") == 3

    def test_get_max_round_none_exist(self, db_session):
        """Test get_max_round returns 0 when no answers exist."""
        repo = AnswerRepository(db_session)
        assert repo.get_max_round("session-1", "q1") == 0

    def test_list_answered(self, db_session):
        """Test list_answered returns only answers with non-null answer_text."""
        _create_test_interview(db_session)
        a1 = _create_test_answer(db_session, question_id="q1", order=1)
        a1.answer_text = "My answer"
        _create_test_answer(db_session, question_id="q2", order=2)  # no text
        a3 = _create_test_answer(db_session, question_id="q3", order=3)
        a3.answer_text = "Another answer"
        db_session.commit()

        repo = AnswerRepository(db_session)
        results = repo.list_answered("session-1")
        assert len(results) == 2
        assert results[0].question_id == "q1"
        assert results[1].question_id == "q3"

    def test_list_by_interview(self, db_session):
        """Test list_by_interview returns all answers ordered."""
        _create_test_interview(db_session)
        _create_test_answer(db_session, question_id="q2", order=2)
        _create_test_answer(db_session, question_id="q1", order=1)
        db_session.commit()

        repo = AnswerRepository(db_session)
        results = repo.list_by_interview("session-1")
        assert len(results) == 2
        assert results[0].question_id == "q1"  # order=1 first
        assert results[1].question_id == "q2"  # order=2 second

    def test_set_answer_text(self, db_session):
        """Test set_answer_text updates the answer text."""
        _create_test_interview(db_session)
        ans = _create_test_answer(db_session)

        repo = AnswerRepository(db_session)
        repo.set_answer_text(ans, "Updated answer")
        db_session.commit()

        reloaded = repo.get_by_interview_question_round("session-1", "q1", 0)
        assert reloaded.answer_text == "Updated answer"

    def test_set_evaluation(self, db_session):
        """Test set_evaluation updates score and feedback."""
        _create_test_interview(db_session)
        ans = _create_test_answer(db_session)

        repo = AnswerRepository(db_session)
        repo.set_evaluation(ans, score=4, feedback="Good answer")
        db_session.commit()

        reloaded = repo.get_by_interview_question_round("session-1", "q1", 0)
        assert reloaded.score == 4
        assert reloaded.feedback == "Good answer"
