# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for domain lifecycle and progress rules."""

import pytest

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.rules.lifecycle import (
    MAX_SCORE_PER_ROUND,
    build_per_question_score_breakdown,
    compute_interview_score,
)
from app.interview.services.rules.progress import (
    find_first_unanswered,
    find_next_unanswered_after,
    find_unanswered_for_question,
    require_active,
)
from app.shared.exceptions import (
    InterviewNotActiveError,
    UnansweredAnswerNotFoundError,
)
from tests.helpers.selection import minimal_selection_spec

_SPEC = minimal_selection_spec()


def _session(*, status: str = "active", answers: list[AnswerRead]) -> InterviewRead:
    """Build an InterviewRead for domain tests."""
    return InterviewRead(
        id="s1",
        status=status,
        locale="en",
        selection_spec=_SPEC,
        question_ids="[]",
        question_count=len(answers),
        question_time_limit_seconds=None,
        answers=answers,
    )


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
    """find_unanswered_for_question returns the open row for a question."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(question_id="q2", order=2, question_text="Q2"),
        ]
    )
    current = find_unanswered_for_question(session, "q2")
    assert current.question_id == "q2"


def test_find_unanswered_for_question_raises():
    """find_unanswered_for_question raises when no open row exists."""
    session = _session(answers=[_answer(answer_text="done")])
    with pytest.raises(UnansweredAnswerNotFoundError):
        find_unanswered_for_question(session, "q1")


def test_find_next_unanswered_after():
    """find_next_unanswered_after skips answered rows."""
    session = _session(
        answers=[
            _answer(answer_text="done"),
            _answer(question_id="q2", order=2, question_text="Q2", answer_text="done"),
            _answer(question_id="q3", order=3, question_text="Q3"),
        ]
    )
    nxt = find_next_unanswered_after(session, 1)
    assert nxt is not None
    assert nxt.question_id == "q3"


def test_require_active():
    """require_active raises when the session is completed."""
    session = _session(status="completed", answers=[])
    with pytest.raises(InterviewNotActiveError):
        require_active(session)


def test_build_per_question_score_breakdown():
    """build_per_question_score_breakdown aggregates per question."""
    session = _session(
        answers=[
            _answer(question_id="q1", answer_text="a", score=4),
            _answer(question_id="q1", round=1, answer_text="b", score=3),
            _answer(
                question_id="q2", order=2, question_text="Q2", answer_text="c", score=5
            ),
        ]
    )
    breakdown = build_per_question_score_breakdown(session)
    assert breakdown["q1"] == {"score": 7, "max": MAX_SCORE_PER_ROUND * 2}
    assert breakdown["q2"] == {"score": 5, "max": MAX_SCORE_PER_ROUND}
