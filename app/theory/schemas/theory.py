# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section read models for services and API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

TheorySectionStatusRead = Literal["active", "completed", "skipped"]


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


class TheorySectionRead(BaseModel):
    """Read-only snapshot of a theory section.

    Attributes:
        id: Theory section primary key.
        interview_id: Parent interview UUID.
        status: Section status.
        locale: Language code for feedback and voice.
        selection_spec: JSON describing tracks, levels, and topic categories.
        question_count: Number of questions in this section.
        task_time_limit_seconds: Per-task time limit, or None when disabled.
        tasks: Theory tasks in display order.
        section_score: Aggregated section score when evaluated.
        section_feedback: Parsed section evaluation payload.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    interview_id: str
    status: TheorySectionStatusRead
    locale: str
    selection_spec: str
    question_count: int
    task_time_limit_seconds: int | None
    tasks: list[TheoryTaskRead]
    section_score: int | None = None
    section_feedback: dict[str, Any] | None = None
