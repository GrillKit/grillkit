# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section page read models."""

from pydantic import BaseModel, ConfigDict, Field

from app.theory.schemas.theory import TheoryTaskRead


class TheoryPageContext(BaseModel):
    """Template context for the theory section panel.

    Attributes:
        answers: All theory task rounds for the chat history.
        current_question: First unanswered task, if any.
        current_answer_id: Primary key of the current task row.
        question_timer_enabled: Whether per-round timer is active.
        question_time_limit_seconds: Configured limit in seconds.
        timer_remaining_seconds: Seconds left on the current round.
        current_round: Follow-up round number for the active task.
        complete: Whether all theory tasks have been answered.
    """

    model_config = ConfigDict(frozen=True)

    answers: list[TheoryTaskRead]
    current_question: TheoryTaskRead | None
    current_answer_id: int | None
    question_timer_enabled: bool
    question_time_limit_seconds: int | None
    timer_remaining_seconds: int | None
    current_round: int = Field(default=0)
    complete: bool = False
