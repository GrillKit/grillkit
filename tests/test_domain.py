# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for domain lifecycle and progress rules."""

import pytest

from app.interview.domain.lifecycle import (
    MAX_SCORE_PER_ROUND,
    build_per_question_score_breakdown,
    compute_interview_score,
)
from app.interview.domain.progress import (
    find_first_unanswered,
    find_next_unanswered_after,
    find_unanswered_for_question,
    require_active,
)
from app.interview.domain.session import AnswerView, InterviewView
from app.shared.domain.exceptions import (
    InterviewNotActiveError,
    InterviewNotFoundError,
    UnansweredAnswerNotFoundError,
)
from tests.helpers.selection import minimal_selection_spec

_SPEC = minimal_selection_spec()


def _session(*, status: str = "active", answers: list[AnswerView]) -> InterviewView:
    """Build an InterviewView for domain tests."""
    return InterviewView(
        id="s1",
        status=status,
        locale="en",
        question_time_limit_seconds=None,
        answers=tuple(answers),
    )


def _answer(**kwargs) -> AnswerView:
    """Build an AnswerView with defaults for domain tests."""
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
    return AnswerView(**defaults)


def test_compute_interview_score():
    """Test compute_interview_score sums scored answers."""
    session = _session(
        answers=[
            _answer(question_id="q1", score=4),
            _answer(question_id="q2", order=2, question_text="Q2", score=3),
        ]
    )
    assert compute_interview_score(session) == 7


def test_find_first_unanswered():
    """find_first_unanswered returns the first row without answer text."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(question_id="q2", order=2, question_text="Q2"),
        ]
    )
    current = find_first_unanswered(session)
    assert current is not None
    assert current.question_id == "q2"


def test_find_unanswered_for_question():
    """find_unanswered_for_question matches question_id and open round."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(round=1, question_text="Q1 follow-up"),
        ]
    )
    current = find_unanswered_for_question(session, "q1")
    assert current.round == 1


def test_find_next_unanswered_after():
    """find_next_unanswered_after skips answered rows after current index."""
    session = _session(
        answers=[
            _answer(question_id="q1", question_text="Q1"),
            _answer(
                question_id="q2",
                order=2,
                question_text="Q2",
                answer_text="done",
            ),
            _answer(question_id="q3", order=3, question_text="Q3"),
        ]
    )
    nxt = find_next_unanswered_after(session, 0)
    assert nxt is not None
    assert nxt.question_id == "q3"


def test_require_active_rejects_completed():
    """require_active raises when interview is not active."""
    session = _session(status="completed", answers=[])
    with pytest.raises(InterviewNotActiveError, match="completed interview"):
        require_active(session)


def test_interview_not_found_error_message():
    """InterviewNotFoundError includes the interview id."""
    err = InterviewNotFoundError("abc-123")
    assert err.interview_id == "abc-123"
    assert "abc-123" in str(err)


def test_unanswered_answer_not_found_error():
    """find_unanswered_for_question raises when all rounds are answered."""
    session = _session(answers=[_answer(answer_text="done")])
    with pytest.raises(UnansweredAnswerNotFoundError):
        find_unanswered_for_question(session, "q1")


def test_build_per_question_score_breakdown():
    """Per-question breakdown matches summed round scores and max per round."""
    session = _session(
        answers=[
            _answer(
                question_id="ds-001",
                answer_text="a",
                score=3,
            ),
            _answer(
                question_id="ds-001",
                round=1,
                question_text="Q1b",
                answer_text="b",
                score=2,
            ),
            _answer(
                question_id="ds-002",
                order=2,
                question_text="Q2",
                answer_text="c",
                score=2,
            ),
        ]
    )
    breakdown = build_per_question_score_breakdown(session)
    assert breakdown["ds-001"]["score"] == 5
    assert breakdown["ds-001"]["max"] == 10
    assert breakdown["ds-002"]["score"] == 2
    assert breakdown["ds-002"]["max"] == MAX_SCORE_PER_ROUND
