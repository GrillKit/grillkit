# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Semantic events emitted by interview application services."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnswerSavedEvent:
    """User answer text was persisted."""


@dataclass(frozen=True)
class EvaluatingEvent:
    """AI evaluation has started."""


@dataclass(frozen=True)
class AnswerFeedbackEvent:
    """AI evaluation finished for one answer round.

    Attributes:
        question_id: YAML question ID.
        order: Display order.
        round: Answer round number.
        follow_up_needed: Whether a follow-up question was created.
        follow_up_text: Follow-up question text when applicable.
        next_question: Next unanswered question payload for the client.
    """

    question_id: str
    order: int
    round: int
    follow_up_needed: bool
    follow_up_text: str | None
    next_question: dict[str, Any] | None


@dataclass(frozen=True)
class InterviewCompletedEvent:
    """Entire interview session was evaluated and marked complete.

    Attributes:
        overall_feedback: Parsed session evaluation payload.
        score: Total session score.
        max_score: Maximum achievable score.
    """

    overall_feedback: dict[str, Any]
    score: int
    max_score: int


InterviewEvent = (
    AnswerSavedEvent | EvaluatingEvent | AnswerFeedbackEvent | InterviewCompletedEvent
)
