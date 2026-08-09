# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for structured coding AI evaluation output."""

from typing import Literal

from pydantic import BaseModel, Field


class CodingAnswerEvaluation(BaseModel):
    """Evaluation of an initial coding submission (round=0).

    Attributes:
        score: Rating 1-5.
        feedback: Detailed feedback on the submission.
        strengths: Key strengths demonstrated.
        weaknesses: Areas for improvement.
        follow_up_needed: Whether a follow-up round is needed.
        follow_up_question: Follow-up prompt text when needed.
        follow_up_mode: Composer mode for the follow-up round.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    follow_up_needed: bool = Field(..., description="Whether a follow-up is needed")
    follow_up_question: str | None = Field(None, description="Follow-up prompt text")
    follow_up_mode: Literal["code", "explanation"] | None = Field(
        None,
        description="Follow-up composer mode when follow_up_needed is true",
    )


class CodingFollowUpEvaluation(BaseModel):
    """Evaluation of a coding follow-up round (round >= 1).

    Attributes:
        score: Rating 1-5 for the follow-up.
        feedback: Detailed feedback.
        needs_further_follow_up: Whether another follow-up is needed.
        follow_up_question: Next follow-up prompt text, if needed.
        follow_up_mode: Composer mode for the next follow-up round.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    needs_further_follow_up: bool = Field(
        ..., description="Whether another follow-up is needed"
    )
    follow_up_question: str | None = Field(
        None, description="Next follow-up prompt text"
    )
    follow_up_mode: Literal["code", "explanation"] | None = Field(
        None,
        description="Follow-up composer mode when needs_further_follow_up is true",
    )
