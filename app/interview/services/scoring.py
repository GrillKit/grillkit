# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Resolve display scores for completed interview read models."""

from __future__ import annotations

from typing import Any

from app.coding.domain.entities import CodingSection
from app.interview.domain.entities import Interview as DomainInterview
from app.interview.services.evaluation_aggregator import SessionEvaluationAggregator
from app.theory.domain.entities import TheorySection


def score_from_overall_feedback(overall_feedback: dict[str, Any] | None) -> int | None:
    """Extract a display score from session evaluation feedback.

    Args:
        overall_feedback: Parsed overall evaluation payload.

    Returns:
        Combined score from nested ``score_breakdown``, or None.
    """
    if overall_feedback is None:
        return None
    breakdown = overall_feedback.get("score_breakdown")
    if not isinstance(breakdown, dict) or not breakdown:
        return None
    return SessionEvaluationAggregator.total_score_from_breakdown(breakdown)


def _section_display_score(section: TheorySection | CodingSection) -> int:
    """Resolve earned points from one section aggregate.

    Args:
        section: Theory or coding section aggregate.

    Returns:
        Best-effort earned score for the section.
    """
    if section.status == "skipped":
        return 0
    if section.section_score is not None:
        return section.section_score
    return section.total_score()


def completed_score_fallback(
    shell: DomainInterview,
    theory: TheorySection | None,
    coding: CodingSection | None,
) -> int | None:
    """Resolve a completed session score from section aggregates when feedback lacks it.

    Args:
        shell: Interview shell aggregate.
        theory: Theory section aggregate, if present.
        coding: Coding section aggregate, if present.

    Returns:
        Combined best-effort score across present sections, or None.
    """
    del shell
    total = 0
    found = False
    for section in (theory, coding):
        if section is None:
            continue
        found = True
        total += _section_display_score(section)
    return total if found else None


def resolve_completed_read_score(
    shell: DomainInterview,
    theory: TheorySection | None,
    coding: CodingSection | None,
) -> int | None:
    """Resolve the display score for a completed session read model.

    Args:
        shell: Interview shell aggregate.
        theory: Theory section aggregate, if present.
        coding: Coding section aggregate, if present.

    Returns:
        Display score from feedback or section totals, or None while active.
    """
    if shell.status != "completed":
        return None
    score = score_from_overall_feedback(shell.overall_feedback)
    if score is not None:
        return score
    return completed_score_fallback(shell, theory, coding)
