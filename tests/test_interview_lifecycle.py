# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview aggregate behavior."""

from datetime import UTC, datetime

import pytest

from app.interview.domain.entities import Answer, Interview
from app.interview.domain.exceptions import (
    AnswerNotFoundError,
    InterviewNotActiveError,
    UnansweredAnswerNotFoundError,
)
from app.interview.domain.serialization import parse_selection_spec
from app.interview.domain.value_objects import (
    InterviewSelection,
    PlannedQuestion,
    TrackSelection,
)
from tests.helpers.selection import minimal_selection_spec

_SPEC = minimal_selection_spec()
_EPOCH = datetime.min.replace(tzinfo=UTC)


def _answer(**kwargs) -> Answer:
    """Build a domain answer with defaults for aggregate tests."""
    defaults = {
        "id": 1,
        "interview_id": "s1",
        "question_id": "q1",
        "order": 1,
        "round": 0,
        "question_text": "Q1",
        "question_code": None,
        "answer_text": None,
        "score": None,
        "feedback": None,
        "started_at": None,
        "created_at": _EPOCH,
    }
    defaults.update(kwargs)
    return Answer(**defaults)


def _session(*, status: str = "active", answers: list[Answer]) -> Interview:
    """Build a domain interview for aggregate behavior tests."""
    return Interview(
        id="s1",
        locale="en",
        selection=parse_selection_spec(_SPEC),
        question_count=len(answers),
        question_ids=tuple(answer.question_id for answer in answers),
        question_time_limit_seconds=None,
        status=status,
        score=None,
        overall_feedback=None,
        started_at=datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC),
        completed_at=None,
        answers=tuple(answers),
    )


def test_total_score():
    """total_score sums scored answers."""
    session = _session(
        answers=[
            _answer(question_id="q1", score=4),
            _answer(id=2, question_id="q2", order=2, question_text="Q2", score=3),
        ]
    )
    assert session.total_score() == 7


def test_find_first_unanswered():
    """find_first_unanswered returns the first row without answer text."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(id=2, question_id="q2", order=2, question_text="Q2"),
        ]
    )
    current = session.find_first_unanswered()
    assert current is not None
    assert current.question_id == "q2"


def test_find_unanswered_for_question():
    """find_unanswered_for_question returns the open row for a question."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(id=2, question_id="q2", order=2, question_text="Q2"),
        ]
    )
    current = session.find_unanswered_for_question("q2")
    assert current.question_id == "q2"


def test_find_unanswered_for_question_raises():
    """find_unanswered_for_question raises when no open row exists."""
    session = _session(answers=[_answer(answer_text="done")])
    with pytest.raises(UnansweredAnswerNotFoundError):
        session.find_unanswered_for_question("q1")


def test_find_next_unanswered_after():
    """find_next_unanswered_after skips answered rows."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(
                id=2,
                question_id="q2",
                order=2,
                question_text="Q2",
                answer_text="done",
            ),
            _answer(id=3, question_id="q3", order=3, question_text="Q3"),
        ]
    )
    nxt = session.find_next_unanswered_after(1)
    assert nxt is not None
    assert nxt.question_id == "q3"


def test_ensure_active():
    """ensure_active raises when the session is completed."""
    session = _session(status="completed", answers=[])
    with pytest.raises(InterviewNotActiveError):
        session.ensure_active()


def test_find_answer_returns_matching_round():
    """find_answer locates a row by question_id and round."""
    session = _session(
        answers=[
            _answer(id=1, question_id="q1", round=0),
            _answer(id=2, question_id="q1", round=1, question_text="Follow-up"),
        ]
    )
    found = session.find_answer("q1", 1)
    assert found.id == 2
    assert found.round == 1


def test_find_answer_raises_when_missing():
    """find_answer raises AnswerNotFoundError for unknown keys."""
    session = _session(answers=[_answer(question_id="q1")])
    with pytest.raises(AnswerNotFoundError):
        session.find_answer("q99", 0)


def test_with_timed_out_round_sets_marker_score_and_feedback():
    """with_timed_out_round records timeout fields on one row."""
    session = _session(
        answers=[
            _answer(id=1, question_id="q1"),
            _answer(id=2, question_id="q2", order=2, question_text="Q2"),
        ]
    )
    updated = session.with_timed_out_round(1, "Time is up.")
    timed = updated.answers[0]
    assert timed.answer_text == Answer.TIME_EXPIRED_ANSWER_TEXT
    assert timed.score == 0
    assert timed.feedback == "Time is up."
    assert updated.answers[1].answer_text is None


def test_with_evaluation_sets_score_and_feedback():
    """with_evaluation updates score and feedback on one round."""
    session = _session(
        answers=[
            _answer(id=1, question_id="q1", answer_text="a"),
            _answer(id=2, question_id="q2", order=2, question_text="Q2"),
        ]
    )
    updated = session.with_evaluation("q1", 0, 4, "Solid answer.")
    evaluated = updated.answers[0]
    assert evaluated.score == 4
    assert evaluated.feedback == "Solid answer."
    assert updated.answers[1].score is None


def test_with_follow_up_appends_new_round():
    """with_follow_up adds an unanswered follow-up row with NEW_ID."""
    session = _session(
        answers=[
            _answer(id=1, question_id="q1", answer_text="a", score=3),
        ]
    )
    updated, pending = session.with_follow_up("q1", "Can you elaborate?")
    assert pending.id == Answer.NEW_ID
    assert pending.round == 1
    assert pending.question_text == "Can you elaborate?"
    assert pending.answer_text is None
    assert len(updated.answers) == 2


def test_max_round_for_question():
    """max_round_for_question returns the highest round for a question."""
    session = _session(
        answers=[
            _answer(id=1, question_id="q1", round=0),
            _answer(id=2, question_id="q1", round=2, question_text="R2"),
        ]
    )
    assert session.max_round_for_question("q1") == 2


def test_with_answer_text_updates_single_row():
    """with_answer_text sets answer_text on one answer without touching others."""
    session = _session(
        answers=[
            _answer(id=1, question_id="q1"),
            _answer(id=2, question_id="q2", order=2, question_text="Q2"),
        ]
    )
    updated = session.with_answer_text(1, "my answer")
    assert updated.answers[0].answer_text == "my answer"
    assert updated.answers[1].answer_text is None


def test_start_timer_for_answer_sets_started_at():
    """start_timer_for_answer activates the timer on the target row only."""
    when = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    session = Interview(
        id="s1",
        locale="en",
        selection=parse_selection_spec(_SPEC),
        question_count=2,
        question_ids=("q1", "q2"),
        question_time_limit_seconds=90,
        status="active",
        score=None,
        overall_feedback=None,
        started_at=datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC),
        completed_at=None,
        answers=(
            _answer(id=1, question_id="q1"),
            _answer(id=2, question_id="q2", order=2, question_text="Q2"),
        ),
    )
    timed = session.start_timer_for_answer(2, when=when)
    assert timed.answers[0].started_at is None
    assert timed.answers[1].started_at == when


def test_per_question_score_breakdown():
    """per_question_score_breakdown aggregates per question."""
    session = _session(
        answers=[
            _answer(question_id="q1", answer_text="a", score=4),
            _answer(question_id="q1", round=1, answer_text="b", score=3),
            _answer(
                question_id="q2", order=2, question_text="Q2", answer_text="c", score=5
            ),
        ]
    )
    breakdown = session.per_question_score_breakdown()
    assert breakdown["q1"] == {
        "score": 7,
        "max": Interview.MAX_SCORE_PER_ROUND * 2,
    }
    assert breakdown["q2"] == {"score": 5, "max": Interview.MAX_SCORE_PER_ROUND}


def _planned_question(
    question_id: str, *, text: str = "What is a list?"
) -> PlannedQuestion:
    return PlannedQuestion(id=question_id, text=text, code=None)


def test_interview_start_builds_active_aggregate():
    """Interview.start creates answer rows and question_ids from the plan."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("data-structures",),
            ),
        )
    )
    session = Interview.start(
        "new-session",
        selection=selection,
        locale="ru",
        planned_questions=(
            _planned_question("ds-001"),
            _planned_question("ds-002", text="Second?"),
        ),
    )

    assert session.status == "active"
    assert session.locale == "ru"
    assert session.question_count == 2
    assert session.question_ids == ("ds-001", "ds-002")
    assert len(session.answers) == 2
    assert session.answers[0].id == Answer.NEW_ID
    assert session.answers[0].order == 1
    assert session.answers[1].question_id == "ds-002"
    assert session.answers[0].started_at is None


def test_interview_start_with_timer_starts_first_round():
    """Interview.start sets started_at on the first answer when a limit is set."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics",),
            ),
        )
    )
    session = Interview.start(
        "timed-session",
        selection=selection,
        locale="en",
        planned_questions=(_planned_question("q1"),),
        question_time_limit_seconds=120,
    )

    assert session.question_time_limit_seconds == 120
    assert session.answers[0].started_at is not None
    assert session.answers[0].started_at == session.started_at


def test_with_session_completed_sets_final_state():
    """with_session_completed marks the session completed with total score."""
    when = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    session = _session(
        answers=[
            _answer(question_id="q1", answer_text="a", score=4),
            _answer(
                question_id="q2", order=2, question_text="Q2", answer_text="b", score=3
            ),
        ]
    )
    completed = session.with_session_completed(
        {"summary": "Solid performance."},
        completed_at=when,
    )

    assert completed.status == "completed"
    assert completed.score == 7
    assert completed.completed_at == when
    assert completed.overall_feedback == {"summary": "Solid performance."}


def test_interview_start_empty_plan_raises():
    """Interview.start rejects an empty question plan."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics",),
            ),
        )
    )
    with pytest.raises(ValueError, match="No questions found"):
        Interview.start(
            "empty",
            selection=selection,
            locale="en",
            planned_questions=(),
        )
