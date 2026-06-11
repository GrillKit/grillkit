# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Dashboard view-model builder for interview history."""

from datetime import UTC, datetime
from typing import Any

from app.coding.repositories.uow import CodingUnitOfWork
from app.interview.domain.serialization import parse_session_spec
from app.interview.domain.value_objects import InterviewSelection, session_mode_label
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.dashboard import DashboardRowRead
from app.interview.schemas.interview import InterviewRead
from app.interview.services.rules.selection import (
    selection_summary_lines,
    session_display_title,
)
from app.theory.domain.entities import TheorySection


class DashboardBuilder:
    """Build dashboard rows and display helpers for interview history."""

    @staticmethod
    def format_local_datetime(dt: datetime | None) -> str:
        """Format a timezone-aware datetime in the local timezone.

        Args:
            dt: UTC or aware datetime, or None.

        Returns:
            Formatted string such as ``18 May 2026, 14:30``, or empty string.
        """
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone().strftime("%d %b %Y, %H:%M")

    @staticmethod
    def interview_display_title(interview: InterviewRead) -> str:
        """Build dashboard/interview page title from selection.

        Args:
            interview: Interview read model.

        Returns:
            Title such as ``Python Interview`` or ``Multi-topic Interview``.
        """
        session = parse_session_spec(interview.selection_spec)
        return session_display_title(session)

    @staticmethod
    def _max_score_from_breakdown(score_breakdown: dict[str, Any]) -> int:
        """Sum maximum points from nested or flat score breakdown payloads.

        Args:
            score_breakdown: Session evaluation breakdown dict.

        Returns:
            Maximum achievable score encoded in the breakdown.
        """
        total = 0
        for key, entry in score_breakdown.items():
            if key == "total" or not isinstance(entry, dict):
                continue
            if key in ("theory", "coding"):
                max_score = entry.get("max")
                if isinstance(max_score, int):
                    total += max_score
                continue
            max_score = entry.get("max")
            if isinstance(max_score, int):
                total += max_score
        return total

    @staticmethod
    def compute_max_score(
        interview: InterviewRead,
        score_breakdown: dict[str, Any] | None = None,
    ) -> int:
        """Compute maximum achievable score for a session.

        Uses AI ``score_breakdown`` when provided; otherwise estimates
        five points per answered theory round or submitted coding round.

        Args:
            interview: Interview read model with answers loaded.
            score_breakdown: Optional per-question breakdown from session evaluation.

        Returns:
            Maximum possible score for the session.
        """
        if score_breakdown:
            breakdown_total = DashboardBuilder._max_score_from_breakdown(
                score_breakdown
            )
            if breakdown_total > 0:
                return breakdown_total

        theory_max = sum(
            TheorySection.MAX_SCORE_PER_ROUND
            for answer in interview.answers
            if answer.answer_text is not None
        )
        if theory_max > 0:
            return theory_max

        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview.id)
            if section is not None:
                return section.max_score()

        return 0

    @staticmethod
    def selection_summary_lines(selection: InterviewSelection) -> list[str]:
        """Build display lines for each track source in a selection.

        Args:
            selection: Interview selection.

        Returns:
            Lines such as ``Python / middle: basics, oop``.
        """
        return selection_summary_lines(selection)

    @staticmethod
    def list_rows(limit: int = 20) -> list[DashboardRowRead]:
        """Load recent interviews for the dashboard history table.

        Args:
            limit: Maximum rows to return.

        Returns:
            Rows sorted newest-first (completed or started time).
        """
        with InterviewUnitOfWork() as uow:
            interviews = uow.interviews.list_recent_read_models(limit=limit)

        rows: list[DashboardRowRead] = []
        for interview in interviews:
            if interview.status == "completed":
                feedback = interview.overall_feedback
                breakdown = feedback.get("score_breakdown") if feedback else None
                max_score = DashboardBuilder.compute_max_score(interview, breakdown)
                score = interview.score if interview.score is not None else 0
                score_display = f"{score} / {max_score}"
                status_label = "Completed"
                when = interview.completed_at
            else:
                score_display = "—"
                status_label = "Active"
                when = interview.started_at

            session = parse_session_spec(interview.selection_spec)
            rows.append(
                DashboardRowRead(
                    id=interview.id,
                    title=DashboardBuilder.interview_display_title(interview),
                    question_count=interview.question_count,
                    session_mode_label=session_mode_label(session.session_mode),
                    score_display=score_display,
                    status=interview.status,
                    status_label=status_label,
                    datetime_display=DashboardBuilder.format_local_datetime(when),
                    url=(
                        f"/interview/{interview.id}/results"
                        if interview.status == "completed"
                        else f"/interview/{interview.id}"
                    ),
                )
            )
        return rows
