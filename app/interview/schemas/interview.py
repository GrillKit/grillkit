# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session read models for services and API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnswerRead(BaseModel):
    """Read-only snapshot of one answer round.

    Attributes:
        id: Answer row primary key.
        question_id: YAML question ID.
        order: Display order within the session (1-based).
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


class InterviewRead(BaseModel):
    """Read-only snapshot of an interview session.

    Attributes:
        id: Interview UUID.
        status: Session status (``active`` or ``completed``).
        locale: Language code for feedback and voice.
        selection_spec: JSON describing tracks, levels, and topic categories.
        question_ids: JSON list of question IDs in display order.
        question_count: Number of questions in this interview.
        question_time_limit_seconds: Per-round time limit, or None when disabled.
        answers: Answer rounds in display order.
        score: Final session score when completed.
        overall_feedback: Parsed overall evaluation payload when completed.
        started_at: When the session began.
        completed_at: When the session ended, or None while active.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    status: str
    locale: str
    selection_spec: str
    question_ids: str
    question_count: int
    question_time_limit_seconds: int | None
    answers: list[AnswerRead]
    score: int | None = None
    overall_feedback: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class InterviewPageContext(BaseModel):
    """Template context for the interview session page.

    Attributes:
        interview: Session read model.
        interview_title: Display title derived from selection.
        selection_lines: Human-readable selection summary lines.
        answers: All answer rounds for the chat history.
        current_question: First unanswered answer, if any.
        current_answer_id: Primary key of the current answer row.
        question_voice_enabled: Whether Piper TTS is enabled in config.
        overall_feedback: Parsed final evaluation for completed sessions.
        max_score: Maximum achievable score for display.
        locale_label: Localized language label.
        question_timer_enabled: Whether per-round timer is active.
        question_time_limit_seconds: Configured limit in seconds.
        timer_remaining_seconds: Seconds left on the current round.
        current_round: Follow-up round number for the active question.
        timeout_chat_label: Localized timeout message for the UI.
        llm_request_timeout_seconds: LLM request timeout from config.
    """

    model_config = ConfigDict(frozen=True)

    interview: InterviewRead
    interview_title: str
    selection_lines: list[str]
    answers: list[AnswerRead]
    current_question: AnswerRead | None
    current_answer_id: int | None
    question_voice_enabled: bool
    overall_feedback: dict[str, Any] | None
    max_score: int
    locale_label: str
    question_timer_enabled: bool
    question_time_limit_seconds: int | None
    timer_remaining_seconds: int | None
    current_round: int
    timeout_chat_label: str
    llm_request_timeout_seconds: int = Field(default=60)
