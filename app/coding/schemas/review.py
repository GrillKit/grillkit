# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section review page read models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CodingTaskRoundRead(BaseModel):
    """Read model for one submitted coding task round.

    Attributes:
        round: Follow-up round number (0 = initial).
        prompt_text: Prompt shown for this round.
        submitted_code: Submitted source code or explanation text.
        score: AI score for the round.
        feedback: AI feedback text for the round.
        submit_test_summary: Hidden test summary after the initial submit.
    """

    model_config = ConfigDict(frozen=True)

    round: int
    prompt_text: str
    submitted_code: str
    score: int | None
    feedback: str | None
    submit_test_summary: dict[str, Any] | None = None


class CodingTaskReviewRead(BaseModel):
    """Read model for one coding task grouped across follow-up rounds.

    Attributes:
        order: Display order within the section (1-based).
        task_id: YAML task ID.
        initial_prompt: Original task prompt from round 0.
        total_score: Sum of round scores for this task.
        max_score: Maximum achievable score for this task.
        rounds: Submitted rounds in ascending round order.
    """

    model_config = ConfigDict(frozen=True)

    order: int
    task_id: str
    initial_prompt: str
    total_score: int
    max_score: int
    rounds: list[CodingTaskRoundRead] = Field(default_factory=list)


class CodingReviewContext(BaseModel):
    """Template context for the completed coding section review page.

    Attributes:
        interview_id: Parent session UUID.
        interview_title: Display title derived from selection.
        selection_lines: Human-readable selection summary lines.
        locale_label: Localized language label.
        section_score: Aggregated section score.
        section_max_score: Maximum achievable section score.
        section_feedback: Resolved section narrative payload.
        tasks: Coding tasks grouped by order with round details.
        results_url: Relative URL for the session results hub.
    """

    model_config = ConfigDict(frozen=True)

    interview_id: str
    interview_title: str
    selection_lines: list[str]
    locale_label: str
    section_score: int
    section_max_score: int
    section_feedback: dict[str, Any]
    tasks: list[CodingTaskReviewRead]
    results_url: str
