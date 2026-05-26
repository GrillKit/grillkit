# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Dashboard view-model builder for interview history."""

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any

from app.interview.domain.lifecycle import MAX_SCORE_PER_ROUND
from app.interview.domain.selection import (
    InterviewSelection,
    get_interview_selection,
    interview_display_title,
    track_label,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import Interview


@dataclass(frozen=True)
class DashboardInterviewRow:
    """Row model for the dashboard interview history table.

    Attributes:
        id: Interview UUID.
        title: Display title (e.g. "Python Interview").
        question_count: Number of questions in the session.
        score_display: Formatted score or em dash when not finished.
        status: Raw status ("active" or "completed").
        status_label: Human-readable status for the UI.
        datetime_display: Localized date/time string for the row.
        url: Link to the interview page.
    """

    id: str
    title: str
    question_count: int
    score_display: str
    status: str
    status_label: str
    datetime_display: str
    url: str


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
    def interview_display_title(interview: Interview) -> str:
        """Build dashboard/interview page title from selection.

        Args:
            interview: Interview instance.

        Returns:
            Title such as ``Python Interview`` or ``Multi-topic Interview``.
        """
        selection = get_interview_selection(interview)
        return interview_display_title(selection)

    @staticmethod
    def parse_overall_feedback(interview: Interview) -> dict[str, Any] | None:
        """Parse ``overall_feedback`` JSON for templates and APIs.

        Args:
            interview: Interview, possibly with raw JSON in ``overall_feedback``.

        Returns:
            Parsed dict, or None if the session has no feedback.
        """
        if not interview.overall_feedback:
            return None
        try:
            parsed = json.loads(interview.overall_feedback)
        except json.JSONDecodeError:
            return {"overall_feedback": interview.overall_feedback}
        if isinstance(parsed, dict):
            return parsed
        return {"overall_feedback": interview.overall_feedback}

    @staticmethod
    def compute_max_score(
        interview: Interview,
        score_breakdown: dict[str, Any] | None = None,
    ) -> int:
        """Compute maximum achievable score for a session.

        Uses AI ``score_breakdown`` when provided; otherwise estimates
        five points per answered round (including follow-ups).

        Args:
            interview: Interview with answers loaded.
            score_breakdown: Optional per-question breakdown from session evaluation.

        Returns:
            Maximum possible score for the session.
        """
        if score_breakdown:
            total = 0
            for qid, breakdown in score_breakdown.items():
                if qid != "total" and isinstance(breakdown, dict):
                    total += breakdown.get("max", MAX_SCORE_PER_ROUND)
            return total

        return sum(
            MAX_SCORE_PER_ROUND
            for answer in interview.answers
            if answer.answer_text is not None
        )

    @staticmethod
    def selection_summary_lines(selection: InterviewSelection) -> list[str]:
        """Build display lines for each track source in a selection.

        Args:
            selection: Interview selection.

        Returns:
            Lines such as ``Python / middle: basics, oop``.
        """
        lines: list[str] = []
        for source in selection.sources:
            label = track_label(source.track)
            topics = ", ".join(
                cat.replace("-", " ").replace("_", " ").title()
                for cat in source.categories
            )
            lines.append(f"{label} / {source.level}: {topics}")
        return lines

    @staticmethod
    def list_rows(limit: int = 20) -> list[DashboardInterviewRow]:
        """Load recent interviews for the dashboard history table.

        Args:
            limit: Maximum rows to return.

        Returns:
            Rows sorted newest-first (completed or started time).
        """
        with InterviewUnitOfWork() as uow:
            interviews = uow.interviews.list_recent(limit=limit)

        rows: list[DashboardInterviewRow] = []
        for interview in interviews:
            if interview.status == "completed":
                feedback = DashboardBuilder.parse_overall_feedback(interview)
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

            rows.append(
                DashboardInterviewRow(
                    id=interview.id,
                    title=DashboardBuilder.interview_display_title(interview),
                    question_count=interview.question_count,
                    score_display=score_display,
                    status=interview.status,
                    status_label=status_label,
                    datetime_display=DashboardBuilder.format_local_datetime(when),
                    url=f"/interview/{interview.id}",
                )
            )
        return rows
