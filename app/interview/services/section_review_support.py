# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for completed section review page context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.interview.domain.serialization import parse_session_spec
from app.interview.domain.value_objects import SessionSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.rules.selection import session_selection_summary_lines
from app.interview.services.section_feedback import resolve_section_feedback
from app.interview.services.sections import SectionEvaluationSummary, SectionKind
from app.shared.locales import SUPPORTED_LOCALES


@dataclass(frozen=True, slots=True)
class CompletedInterviewSnapshot:
    """Loaded completed interview shell for section review pages.

    Attributes:
        interview: Completed interview read model.
        session: Parsed session selection from ``selection_spec``.
    """

    interview: InterviewRead
    session: SessionSelection


def load_completed_interview(interview_id: str) -> CompletedInterviewSnapshot | None:
    """Load a completed interview read model in one unit-of-work.

    Args:
        interview_id: Parent session UUID.

    Returns:
        Snapshot for review rendering, or None when missing or still active.
    """
    with InterviewUnitOfWork() as uow:
        interview = uow.interviews.get_read_model(interview_id)
        if interview is None or interview.status != "completed":
            return None
        session = parse_session_spec(interview.selection_spec)
        return CompletedInterviewSnapshot(interview=interview, session=session)


def section_score_bounds(
    *,
    skipped: bool,
    total_score: int,
    max_score: int,
) -> tuple[int, int]:
    """Normalize section score bounds for skipped sections.

    Args:
        skipped: Whether the section was skipped at session end.
        total_score: Earned section points.
        max_score: Maximum achievable section points.

    Returns:
        Tuple of display score and max score.
    """
    if skipped:
        return 0, 0
    return total_score, max_score


def shared_review_fields(
    interview_id: str,
    snapshot: CompletedInterviewSnapshot,
) -> dict[str, Any]:
    """Build review context fields shared by theory and coding pages.

    Args:
        interview_id: Parent session UUID.
        snapshot: Completed interview snapshot.

    Returns:
        Dict with title, selection lines, locale label, and results URL.
    """
    interview = snapshot.interview
    return {
        "interview_id": interview_id,
        "interview_title": DashboardBuilder.interview_display_title(interview),
        "selection_lines": session_selection_summary_lines(snapshot.session),
        "locale_label": SUPPORTED_LOCALES.get(interview.locale, interview.locale),
        "results_url": f"/interview/{interview_id}/results",
    }


def resolved_section_feedback(
    summary: SectionEvaluationSummary,
    *,
    item_id_key: str,
    cached_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve section narrative feedback from cache or per-task rows.

    Args:
        summary: Section evaluation summary from query services.
        item_id_key: Identifier field name in summary item rows.
        cached_payload: Persisted section feedback payload, if any.

    Returns:
        Section feedback dict for templates.
    """
    return resolve_section_feedback(
        cached_payload,
        summary.items,
        item_id_key=item_id_key,
    )


def review_score_fields(
    summary: SectionEvaluationSummary,
    *,
    total_score: int,
    max_score: int,
) -> dict[str, int]:
    """Build normalized score fields for section review templates.

    Args:
        summary: Section evaluation summary.
        total_score: Earned points from the section aggregate.
        max_score: Maximum achievable points from the section aggregate.

    Returns:
        Dict with ``section_score`` and ``section_max_score``.
    """
    score, section_max = section_score_bounds(
        skipped=summary.skipped,
        total_score=total_score,
        max_score=max_score,
    )
    return {
        "section_score": score,
        "section_max_score": section_max,
    }


def item_id_key_for(section_kind: SectionKind) -> str:
    """Return the item identifier field for a section kind.

    Args:
        section_kind: Section kind identifier.

    Returns:
        ``question_id`` for theory or ``task_id`` for coding.
    """
    return "question_id" if section_kind == "theory" else "task_id"
