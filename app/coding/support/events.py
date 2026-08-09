# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Semantic events emitted by coding application services."""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class CodingFeedbackEvent:
    """AI evaluation finished for one coding task round.

    Attributes:
        task_id: YAML task ID.
        order: Display order within the section.
        round: Task round number.
        follow_up_needed: Whether a follow-up round was created.
        follow_up_text: Follow-up prompt when applicable.
        follow_up_mode: Composer mode for the follow-up round.
        next_task: Next task payload for the client, if any.
        feedback: Short feedback for the client.
        timer_remaining_seconds: Seconds left on the next round timer, if any.
    """

    task_id: str
    order: int
    round: int
    follow_up_needed: bool
    follow_up_text: str | None
    follow_up_mode: Literal["code", "explanation"] | None
    next_task: dict[str, Any] | None
    feedback: str | None = None
    timer_remaining_seconds: int | None = None
