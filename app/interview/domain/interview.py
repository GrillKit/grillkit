# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Domain view models for interview sessions (decoupled from ORM)."""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.infrastructure.models import Answer, Interview


@dataclass(frozen=True)
class AnswerView:
    """Read-only snapshot of one answer round for domain rules.

    Attributes:
        id: Answer row primary key.
        question_id: YAML question ID.
        order: Display order within the session (1-based).
        round: Follow-up round number (0 = initial).
        question_text: Question text shown to the user.
        question_code: Optional code snippet for the question.
        answer_text: User answer text, or None when unanswered.
        score: AI score for the round, or None when not evaluated.
        started_at: When the round timer started, or None.
    """

    id: int
    question_id: str
    order: int
    round: int
    question_text: str
    question_code: str | None
    answer_text: str | None
    score: int | None
    started_at: datetime | None


@dataclass(frozen=True)
class InterviewView:
    """Read-only snapshot of an interview session for domain rules.

    Attributes:
        id: Interview UUID.
        status: Session status (``active`` or ``completed``).
        locale: Language code for feedback and voice.
        question_time_limit_seconds: Per-round time limit, or None when disabled.
        answers: Answer rounds in display order.
        score: Final session score when completed.
        overall_feedback: Raw JSON feedback string when completed.
    """

    id: str
    status: str
    locale: str
    question_time_limit_seconds: int | None
    answers: tuple[AnswerView, ...]
    score: int | None = None
    overall_feedback: str | None = None


def answer_view(answer: "Answer") -> AnswerView:
    """Map an ORM answer row to a domain view.

    Args:
        answer: SQLAlchemy Answer instance.

    Returns:
        Immutable AnswerView for domain helpers.
    """
    return AnswerView(
        id=answer.id,
        question_id=answer.question_id,
        order=answer.order,
        round=answer.round,
        question_text=answer.question_text,
        question_code=answer.question_code,
        answer_text=answer.answer_text,
        score=answer.score,
        started_at=answer.started_at,
    )


def interview_view(interview: "Interview") -> InterviewView:
    """Map an ORM interview row to a domain view.

    Args:
        interview: SQLAlchemy Interview with answers loaded.

    Returns:
        Immutable InterviewView for domain helpers.
    """
    return InterviewView(
        id=interview.id,
        status=interview.status,
        locale=interview.locale,
        question_time_limit_seconds=interview.question_time_limit_seconds,
        answers=tuple(answer_view(a) for a in interview.answers),
        score=interview.score,
        overall_feedback=interview.overall_feedback,
    )
