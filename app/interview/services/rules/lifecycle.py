# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session lifecycle scoring helpers for interview services."""

from collections import defaultdict
from typing import Any

from app.interview.schemas.interview import AnswerRead, InterviewRead

MAX_SCORE_PER_ROUND = 5


def compute_interview_score(interview: InterviewRead) -> int:
    """Sum scores from all answered rounds in a session.

    Args:
        interview: Interview session read model with answers loaded.

    Returns:
        Total score, or 0 if no scored answers exist.
    """
    scores = [answer.score for answer in interview.answers if answer.score is not None]
    return sum(scores) if scores else 0


def build_per_question_score_breakdown(interview: InterviewRead) -> dict[str, Any]:
    """Aggregate earned and maximum scores per question from persisted answers.

    Each answered round (non-empty ``answer_text``) contributes up to five
    points of maximum score. Earned points are the sum of stored per-round
    scores (treating missing scores as zero).

    Args:
        interview: Interview session read model with answers (may be empty).

    Returns:
        Mapping ``question_id`` → ``{"score": int, "max": int}`` for questions
        with at least one answered round. Skipped questions (no submitted text)
        are omitted.
    """
    rounds_by_question: defaultdict[str, list[AnswerRead]] = defaultdict(list)
    for answer in interview.answers:
        if answer.answer_text is not None:
            rounds_by_question[answer.question_id].append(answer)

    breakdown: dict[str, Any] = {}
    for question_id, rounds in rounds_by_question.items():
        earned = sum((r.score or 0) for r in rounds)
        maximum = MAX_SCORE_PER_ROUND * len(rounds)
        breakdown[question_id] = {"score": earned, "max": maximum}
    return breakdown
