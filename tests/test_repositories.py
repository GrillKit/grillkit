# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the repository layer (base, session, answer)."""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Answer, InterviewSession
from app.repositories.answer import AnswerRepository
from app.repositories.base import SqlAlchemyRepository
from app.repositories.session import InterviewSessionRepository


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


def _create_test_session(db_session, session_id="session-1") -> InterviewSession:
    sess = InterviewSession(
        id=session_id,
        level="junior",
        category="python",
        question_count=3,
        question_ids='["q1","q2","q3"]',
        status="active",
    )
    db_session.add(sess)
    db_session.commit()
    return sess


def _create_test_answer(
    db_session,
    session_id="session-1",
    question_id="q1",
    order=1,
    round_num=0,
    question_text="What is Python?",
) -> Answer:
    ans = Answer(
        interview_session_id=session_id,
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


class _ConcreteRepo(SqlAlchemyRepository[InterviewSession]):
    """Concrete subclass for testing the base repository."""

    _model = InterviewSession


class TestSqlAlchemyRepository:
    """Tests for the generic SQLAlchemy repository base."""

    def test_add_and_get(self, db_session):
        """Test adding an entity and retrieving it by ID."""
        repo = _ConcreteRepo(db_session)
        session = InterviewSession(
            id="test-1", level="junior", category="python"
        )
        repo.add(session)
        db_session.commit()

        result = repo.get("test-1")
        assert result is not None
        assert result.id == "test-1"
        assert result.level == "junior"

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
        repo.add(InterviewSession(id="a1", level="junior", category="python"))
        repo.add(InterviewSession(id="a2", level="middle", category="ds"))
        db_session.commit()

        results = repo.list_all()
        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {"a1", "a2"}


# ======================================================================
# InterviewSessionRepository
# ======================================================================


class TestInterviewSessionRepository:
    """Tests for InterviewSessionRepository."""

    def test_get_eager_loads_answers(self, db_session):
        """Test get() eagerly loads the answers relationship."""
        _create_test_session(db_session)
        _create_test_answer(db_session)

        repo = InterviewSessionRepository(db_session)
        session = repo.get("session-1")
        assert session is not None
        # answers should be loaded (no lazy-load error)
        assert len(session.answers) == 1

    def test_get_by_id_with_answers(self, db_session):
        """Test explicit alias for get()."""
        _create_test_session(db_session)
        repo = InterviewSessionRepository(db_session)
        session = repo.get_by_id_with_answers("session-1")
        assert session is not None
        assert session.id == "session-1"

    def test_new_session_factory(self, db_session):
        """Test new_session() factory method."""
        sess = InterviewSessionRepository.new_session(
            session_id="new-id",
            level="senior",
            category="system-design",
            question_count=5,
            question_ids=["ds-001", "ds-002"],
        )
        assert sess.id == "new-id"
        assert sess.level == "senior"
        assert sess.question_ids == json.dumps(["ds-001", "ds-002"])
        assert sess.status == "active"

    def test_new_session_has_no_id_in_db(self, db_session):
        """Test new_session() does not persist automatically."""
        sess = InterviewSessionRepository.new_session(
            session_id="new-id",
            level="junior",
            category="python",
            question_count=3,
            question_ids=["q1"],
        )
        repo = InterviewSessionRepository(db_session)
        assert repo.get("new-id") is None

    def test_complete_session(self, db_session):
        """Test complete_session() marks session as completed with score."""
        _create_test_session(db_session)
        a1 = _create_test_answer(db_session, question_id="q1")
        a1.score = 4
        a2 = _create_test_answer(db_session, question_id="q2")
        a2.score = 3
        db_session.commit()

        repo = InterviewSessionRepository(db_session)
        session = repo.get("session-1")

        repo.complete_session(session)

        assert session.status == "completed"
        assert session.score == 7  # 4 + 3
        assert session.completed_at is not None
        assert isinstance(session.completed_at, datetime)

    def test_complete_session_no_scores(self, db_session):
        """Test complete_session with no scored answers."""
        _create_test_session(db_session)
        _create_test_answer(db_session, question_id="q1")

        repo = InterviewSessionRepository(db_session)
        session = repo.get("session-1")

        repo.complete_session(session)
        assert session.score == 0
        assert session.status == "completed"

    def test_complete_session_with_feedback(self, db_session):
        """Test complete_session with overall_feedback_json."""
        _create_test_session(db_session)
        repo = InterviewSessionRepository(db_session)
        session = repo.get("session-1")

        feedback = '{"overall": "Good job"}'
        repo.complete_session(session, overall_feedback_json=feedback)
        assert session.overall_feedback == feedback

    def test_save_evaluation_feedback(self, db_session):
        """Test save_evaluation_feedback() sets overall_feedback."""
        _create_test_session(db_session)
        repo = InterviewSessionRepository(db_session)
        session = repo.get("session-1")

        repo.save_evaluation_feedback(session, '{"score": 42}')
        assert session.overall_feedback == '{"score": 42}'

    def test_get_not_found(self, db_session):
        """Test get returns None for missing ID."""
        repo = InterviewSessionRepository(db_session)
        assert repo.get("nope") is None


# ======================================================================
# AnswerRepository
# ======================================================================


class TestAnswerRepository:
    """Tests for AnswerRepository."""

    def test_get_by_session_question_round(self, db_session):
        """Test finding an answer by session, question, and round."""
        _create_test_session(db_session)
        _create_test_answer(db_session, question_id="q1", round_num=0)
        _create_test_answer(db_session, question_id="q1", round_num=1)

        repo = AnswerRepository(db_session)
        ans0 = repo.get_by_session_question_round("session-1", "q1", 0)
        ans1 = repo.get_by_session_question_round("session-1", "q1", 1)

        assert ans0 is not None
        assert ans0.round == 0
        assert ans1 is not None
        assert ans1.round == 1

    def test_get_by_session_question_round_not_found(self, db_session):
        """Test returns None when no answer matches."""
        repo = AnswerRepository(db_session)
        result = repo.get_by_session_question_round("s1", "q99", 0)
        assert result is None

    def test_get_by_session_question_round_raise(self, db_session):
        """Test the raise variant on missing answer."""
        repo = AnswerRepository(db_session)
        with pytest.raises(ValueError, match="Answer not found"):
            repo.get_by_session_question_round_raise("s1", "q99", 0)

    def test_get_by_session_question_round_raise_found(self, db_session):
        """Test the raise variant returns answer on success."""
        _create_test_session(db_session)
        _create_test_answer(db_session, question_id="q1")
        repo = AnswerRepository(db_session)
        ans = repo.get_by_session_question_round_raise("session-1", "q1", 0)
        assert ans.question_id == "q1"

    def test_get_max_round(self, db_session):
        """Test get_max_round returns highest round number."""
        _create_test_session(db_session)
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
        _create_test_session(db_session)
        a1 = _create_test_answer(db_session, question_id="q1", order=1)
        a1.answer_text = "My answer"
        a2 = _create_test_answer(db_session, question_id="q2", order=2)  # no text
        a3 = _create_test_answer(db_session, question_id="q3", order=3)
        a3.answer_text = "Another answer"
        db_session.commit()

        repo = AnswerRepository(db_session)
        results = repo.list_answered("session-1")
        assert len(results) == 2
        assert results[0].question_id == "q1"
        assert results[1].question_id == "q3"

    def test_list_by_session(self, db_session):
        """Test list_by_session returns all answers ordered."""
        _create_test_session(db_session)
        a1 = _create_test_answer(db_session, question_id="q2", order=2)
        a2 = _create_test_answer(db_session, question_id="q1", order=1)
        db_session.commit()

        repo = AnswerRepository(db_session)
        results = repo.list_by_session("session-1")
        assert len(results) == 2
        assert results[0].question_id == "q1"  # order=1 first
        assert results[1].question_id == "q2"  # order=2 second

    def test_set_answer_text(self, db_session):
        """Test set_answer_text updates the answer text."""
        _create_test_session(db_session)
        ans = _create_test_answer(db_session)

        repo = AnswerRepository(db_session)
        repo.set_answer_text(ans, "Updated answer")
        db_session.commit()

        reloaded = repo.get_by_session_question_round("session-1", "q1", 0)
        assert reloaded is not None
        assert reloaded.answer_text == "Updated answer"

    def test_set_evaluation(self, db_session):
        """Test set_evaluation updates score and feedback."""
        _create_test_session(db_session)
        ans = _create_test_answer(db_session)

        repo = AnswerRepository(db_session)
        repo.set_evaluation(ans, score=4, feedback="Good answer")
        db_session.commit()

        reloaded = repo.get_by_session_question_round("session-1", "q1", 0)
        assert reloaded is not None
        assert reloaded.score == 4
        assert reloaded.feedback == "Good answer"

    def test_new_answer_factory(self, db_session):
        """Test new_answer() factory method."""
        ans = AnswerRepository.new_answer(
            session_id="s1",
            question_id="q1",
            order=1,
            round_num=0,
            question_text="What?",
            question_code="print(1)",
        )
        assert ans.interview_session_id == "s1"
        assert ans.question_code == "print(1)"
        assert ans.round == 0

    def test_new_follow_up(self, db_session):
        """Test new_follow_up creates a follow-up from original."""
        _create_test_session(db_session)
        original = _create_test_answer(
            db_session, question_id="q1", order=1, round_num=0
        )

        follow_up = AnswerRepository.new_follow_up(
            original, follow_up_text="Follow-up?", next_round=1
        )
        assert follow_up.interview_session_id == "session-1"
        assert follow_up.question_id == "q1"
        assert follow_up.order == 1
        assert follow_up.round == 1
        assert follow_up.question_text == "Follow-up?"
        assert follow_up.question_code == original.question_code

    def test_new_follow_up_not_persisted(self, db_session):
        """Test new_follow_up does not auto-persist."""
        _create_test_session(db_session)
        original = _create_test_answer(db_session)
        follow_up = AnswerRepository.new_follow_up(
            original, "Follow-up?", 1
        )

        repo = AnswerRepository(db_session)
        assert repo.get_by_session_question_round("session-1", "q1", 1) is None
