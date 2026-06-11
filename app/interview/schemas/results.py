# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session results page read models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.interview.schemas.interview import InterviewRead


class SectionResultCard(BaseModel):
    """Summary card for one completed interview section on the results hub.

    Attributes:
        section: Section kind identifier.
        label: Human-readable section title.
        score: Earned points for the section.
        max_score: Maximum achievable points for the section.
        skipped: True when the user ended before finishing the section.
        summary: Short narrative excerpt for the card.
        detail_url: Relative URL for the section review page.
    """

    model_config = ConfigDict(frozen=True)

    section: Literal["theory", "coding"]
    label: str
    score: int
    max_score: int
    skipped: bool
    summary: str
    detail_url: str


class SessionResultsContext(BaseModel):
    """Template context for the completed session results hub.

    Attributes:
        interview: Completed session read model.
        interview_title: Display title derived from selection.
        selection_lines: Human-readable selection summary lines.
        session_mode_label: Localized session mode label.
        locale_label: Localized language label.
        max_score: Maximum achievable score for the session.
        overall_feedback: Parsed final evaluation payload.
        section_cards: Per-section summary cards in phase order.
        theory_review_url: Theory review URL when theory is enabled.
        coding_review_url: Coding review URL when coding is enabled.
    """

    model_config = ConfigDict(frozen=True)

    interview: InterviewRead
    interview_title: str
    selection_lines: list[str]
    session_mode_label: str
    locale_label: str
    max_score: int
    overall_feedback: dict[str, Any]
    section_cards: list[SectionResultCard]
    theory_review_url: str | None = None
    coding_review_url: str | None = None
