# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Dashboard view-model builder for interview history."""

from datetime import UTC, datetime
from typing import Any

from app.interview.domain.entities import Interview
from app.interview.domain.value_objects import InterviewSelection
from app.interview.repositories.mappers import interview_from_orm, interview_to_read
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.dashboard import DashboardRowRead
from app.interview.schemas.interview import InterviewRead
from app.interview.services.rules.selection import (
    get_interview_selection,
    interview_display_title,
    track_label,
)


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
        selection = get_interview_selection(interview)
        return interview_display_title(selection)

    @staticmethod
    def parse_overall_feedback(interview: InterviewRead) -> dict[str, Any] | None:
        """Return parsed overall feedback for templates and APIs.

        Args:
            interview: Interview read model.

        Returns:
            Parsed dict, or None if the session has no feedback.
        """
        return interview.overall_feedback

    @staticmethod
    def compute_max_score(
        interview: InterviewRead,
        score_breakdown: dict[str, Any] | None = None,
    ) -> int:
        """Compute maximum achievable score for a session.

        Uses AI ``score_breakdown`` when provided; otherwise estimates
        five points per answered round (including follow-ups).

        Args:
            interview: Interview read model with answers loaded.
            score_breakdown: Optional per-question breakdown from session evaluation.

        Returns:
            Maximum possible score for the session.
        """
        if score_breakdown:
            total = 0
            for qid, breakdown in score_breakdown.items():
                if qid != "total" and isinstance(breakdown, dict):
                    total += breakdown.get("max", Interview.MAX_SCORE_PER_ROUND)
            return total

        return sum(
            Interview.MAX_SCORE_PER_ROUND
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
    def list_rows(limit: int = 20) -> list[DashboardRowRead]:
        """Load recent interviews for the dashboard history table.

        Args:
            limit: Maximum rows to return.

        Returns:
            Rows sorted newest-first (completed or started time).
        """
        with InterviewUnitOfWork() as uow:
            interviews = uow.interviews.list_recent(limit=limit)

        rows: list[DashboardRowRead] = []
        for interview_orm in interviews:
            interview = interview_to_read(interview_from_orm(interview_orm))
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
                DashboardRowRead(
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
