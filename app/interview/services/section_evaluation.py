# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for building per-section evaluation summaries."""

from __future__ import annotations

from typing import Any

from app.interview.domain.value_objects import SectionKind
from app.interview.services.sections import SectionEvaluationSummary


def build_section_evaluation_summary(
    section_kind: SectionKind,
    *,
    section_status: str,
    items: tuple[dict[str, Any], ...],
    total_score: int,
    max_score: int,
    cached_narrative: dict[str, Any] | None,
) -> SectionEvaluationSummary:
    """Build a ``SectionEvaluationSummary`` from section aggregate fields.

    Args:
        section_kind: Section kind identifier.
        section_status: Persisted section status string.
        items: Per-task evaluation rows for the section.
        total_score: Earned points before skip normalization.
        max_score: Maximum achievable points before skip normalization.
        cached_narrative: Cached section feedback payload, if any.

    Returns:
        Normalized section evaluation summary for session completion.
    """
    skipped = section_status == "skipped"
    return SectionEvaluationSummary(
        section=section_kind,
        score=0 if skipped else total_score,
        max_score=0 if skipped else max_score,
        items=items,
        cached_narrative=cached_narrative,
        skipped=skipped,
    )
