# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for structured theory AI evaluation output."""

from pydantic import BaseModel, Field

from app.shared.evaluation_models import InterviewEvaluation, SectionEvaluation

__all__ = [
    "AnswerEvaluation",
    "FollowUpEvaluation",
    "InterviewEvaluation",
    "SectionEvaluation",
]


class AnswerEvaluation(BaseModel):
    """Evaluation of a single initial answer (round=0).

    Attributes:
        score: Rating 1-5.
        feedback: Detailed feedback on the answer.
        strengths: Key strengths demonstrated.
        weaknesses: Areas for improvement.
        follow_up_needed: Whether a follow-up question is needed.
        follow_up_question: The follow-up question text, if needed.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    follow_up_needed: bool = Field(..., description="Whether a follow-up is needed")
    follow_up_question: str | None = Field(None, description="Follow-up question text")


class FollowUpEvaluation(BaseModel):
    """Evaluation of a follow-up answer (round >= 1).

    Attributes:
        score: Rating 1-5 for the follow-up.
        feedback: Detailed feedback.
        needs_further_follow_up: Whether another follow-up is needed.
        follow_up_question: Next follow-up question text, if needed.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    needs_further_follow_up: bool = Field(
        ..., description="Whether another follow-up is needed"
    )
    follow_up_question: str | None = Field(
        None, description="Next follow-up question text"
    )
