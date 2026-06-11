# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section review page read models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.theory.schemas.theory import TheoryTaskRead


class TheoryReviewContext(BaseModel):
    """Template context for the completed theory section review page.

    Attributes:
        interview_id: Parent session UUID.
        interview_title: Display title derived from selection.
        selection_lines: Human-readable selection summary lines.
        locale_label: Localized language label.
        section_score: Aggregated section score.
        section_max_score: Maximum achievable section score.
        section_feedback: Resolved section narrative payload.
        answers: All answered theory task rounds for chat history.
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
    answers: list[TheoryTaskRead]
    results_url: str
