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
from app.shared.domain.exceptions import (
    InterviewNotActiveError,
    InterviewNotFoundError,
    UnansweredAnswerNotFoundError,
)
from app.shared.infrastructure.models import Answer, Interview


def test_compute_interview_score():
    """Test compute_interview_score sums scored answers."""
    session = Interview(id="s1", level="junior", category="python")
    session.answers = [
        Answer(
            interview_id="s1",
            question_id="q1",
            order=1,
            round=0,
            question_text="Q1",
            score=4,
        ),
        Answer(
            interview_id="s1",
            question_id="q2",
            order=2,
            round=0,
            question_text="Q2",
            score=3,
        ),
    ]
    assert compute_interview_score(session) == 7


def test_find_first_unanswered():
    """find_first_unanswered returns the first row without answer text."""
    interview = Interview(id="s1", level="junior", category="python")
    interview.answers = [
        Answer(
            interview_id="s1",
            question_id="q1",
            order=1,
            round=0,
            question_text="Q1",
            answer_text="done",
        ),
        Answer(
            interview_id="s1",
            question_id="q2",
            order=2,
            round=0,
            question_text="Q2",
        ),
    ]
    current = find_first_unanswered(interview)
    assert current is not None
    assert current.question_id == "q2"


def test_find_unanswered_for_question():
    """find_unanswered_for_question matches question_id and open round."""
    interview = Interview(id="s1", level="junior", category="python")
    interview.answers = [
        Answer(
            interview_id="s1",
            question_id="q1",
            order=1,
            round=0,
            question_text="Q1",
            answer_text="done",
        ),
        Answer(
            interview_id="s1",
            question_id="q1",
            order=1,
            round=1,
            question_text="Q1 follow-up",
        ),
    ]
    current = find_unanswered_for_question(interview, "q1")
    assert current.round == 1


def test_find_next_unanswered_after():
    """find_next_unanswered_after skips answered rows after current index."""
    interview = Interview(id="s1", level="junior", category="python")
    interview.answers = [
        Answer(
            interview_id="s1",
            question_id="q1",
            order=1,
            round=0,
            question_text="Q1",
        ),
        Answer(
            interview_id="s1",
            question_id="q2",
            order=2,
            round=0,
            question_text="Q2",
            answer_text="done",
        ),
        Answer(
            interview_id="s1",
            question_id="q3",
            order=3,
            round=0,
            question_text="Q3",
        ),
    ]
    nxt = find_next_unanswered_after(interview, 0)
    assert nxt is not None
    assert nxt.question_id == "q3"


def test_require_active_rejects_completed():
    """require_active raises when interview is not active."""
    interview = Interview(
        id="s1", level="junior", category="python", status="completed"
    )
    with pytest.raises(InterviewNotActiveError, match="completed interview"):
        require_active(interview)


def test_interview_not_found_error_message():
    """InterviewNotFoundError includes the interview id."""
    err = InterviewNotFoundError("abc-123")
    assert err.interview_id == "abc-123"
    assert "abc-123" in str(err)


def test_unanswered_answer_not_found_error():
    """find_unanswered_for_question raises when all rounds are answered."""
    interview = Interview(id="s1", level="junior", category="python")
    interview.answers = [
        Answer(
            interview_id="s1",
            question_id="q1",
            order=1,
            round=0,
            question_text="Q1",
            answer_text="done",
        ),
    ]
    with pytest.raises(UnansweredAnswerNotFoundError):
        find_unanswered_for_question(interview, "q1")


def test_build_per_question_score_breakdown():
    """Per-question breakdown matches summed round scores and max per round."""
    session = Interview(
        id="s1",
        level="junior",
        language="python",
        category="python",
    )
    session.answers = [
        Answer(
            interview_id="s1",
            question_id="ds-001",
            order=1,
            round=0,
            question_text="Q1",
            answer_text="a",
            score=3,
        ),
        Answer(
            interview_id="s1",
            question_id="ds-001",
            order=1,
            round=1,
            question_text="Q1b",
            answer_text="b",
            score=2,
        ),
        Answer(
            interview_id="s1",
            question_id="ds-002",
            order=2,
            round=0,
            question_text="Q2",
            answer_text="c",
            score=2,
        ),
    ]
    breakdown = build_per_question_score_breakdown(session)
    assert breakdown["ds-001"]["score"] == 5
    assert breakdown["ds-001"]["max"] == 10
    assert breakdown["ds-002"]["score"] == 2
    assert breakdown["ds-002"]["max"] == MAX_SCORE_PER_ROUND
