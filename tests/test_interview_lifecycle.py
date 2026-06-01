# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview aggregate behavior."""

import pytest

from app.interview.domain.entities import Interview
from app.interview.domain.exceptions import (
    InterviewNotActiveError,
    UnansweredAnswerNotFoundError,
)
from app.interview.repositories.mappers import interview_read_to_domain
from app.interview.schemas.interview import AnswerRead, InterviewRead
from tests.helpers.selection import minimal_selection_spec

_SPEC = minimal_selection_spec()


def _session(*, status: str = "active", answers: list[AnswerRead]) -> Interview:
    """Build a domain interview from a read-model fixture."""
    read = InterviewRead(
        id="s1",
        status=status,
        locale="en",
        selection_spec=_SPEC,
        question_ids="[]",
        question_count=len(answers),
        question_time_limit_seconds=None,
        answers=answers,
    )
    return interview_read_to_domain(read)


def _answer(**kwargs) -> AnswerRead:
    """Build an AnswerRead with defaults for domain tests."""
    defaults = {
        "id": 1,
        "question_id": "q1",
        "order": 1,
        "round": 0,
        "question_text": "Q1",
        "question_code": None,
        "answer_text": None,
        "score": None,
        "started_at": None,
    }
    defaults.update(kwargs)
    return AnswerRead(**defaults)


def test_total_score():
    """total_score sums scored answers."""
    session = _session(
        answers=[
            _answer(question_id="q1", score=4),
            _answer(question_id="q2", order=2, question_text="Q2", score=3),
        ]
    )
    assert session.total_score() == 7


def test_find_first_unanswered():
    """find_first_unanswered returns the first row without answer text."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(question_id="q2", order=2, question_text="Q2"),
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
            _answer(question_id="q2", order=2, question_text="Q2"),
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
            _answer(question_id="q2", order=2, question_text="Q2", answer_text="done"),
            _answer(question_id="q3", order=3, question_text="Q3"),
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
