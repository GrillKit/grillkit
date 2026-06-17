# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section read models for services and API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TheoryTaskRead(BaseModel):
    """Read-only snapshot of one theory task round.

    Attributes:
        id: Task row primary key.
        question_id: YAML question ID.
        order: Display order within the section (1-based).
        round: Follow-up round number (0 = initial).
        question_text: Question text shown to the user.
        question_code: Optional code snippet for the question.
        answer_text: User answer text, or None when unanswered.
        score: AI score for the round, or None when not evaluated.
        feedback: AI-generated feedback text, or None.
        started_at: When the round timer started, or None.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    question_id: str
    order: int
    round: int
    question_text: str
    question_code: str | None
    answer_text: str | None
    score: int | None
    feedback: str | None = None
    started_at: datetime | None
