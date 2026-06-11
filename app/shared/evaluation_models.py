# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared Pydantic models for structured session and section AI evaluation."""

from typing import Any

from pydantic import BaseModel, Field


class SectionEvaluation(BaseModel):
    """Narrative evaluation for a single theory or coding section.

    Attributes:
        section_feedback: Section-level narrative feedback.
        topics_to_review: Topics the candidate should study further.
        strengths_summary: Key strengths demonstrated in the section.
        score_breakdown: Per-task score breakdown for the section.
    """

    section_feedback: str = Field(..., description="Section narrative feedback")
    topics_to_review: list[str] = Field(default_factory=list)
    strengths_summary: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class InterviewEvaluation(BaseModel):
    """Final evaluation of an entire interview session.

    Attributes:
        overall_feedback: Comprehensive narrative feedback on the session.
        topics_to_review: Topics the candidate should study further.
        strengths_summary: Key strengths demonstrated.
        score_breakdown: Per-section and per-task score breakdown.
    """

    overall_feedback: str = Field(..., description="Comprehensive feedback")
    topics_to_review: list[str] = Field(default_factory=list)
    strengths_summary: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
