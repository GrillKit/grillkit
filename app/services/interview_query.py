# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session query service.

Read-only helpers for loading sessions and preparing view data.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any

from app.domain.exceptions import InterviewNotFoundError
from app.domain.interview_lifecycle import MAX_SCORE_PER_ROUND
from app.domain.interview_progress import find_first_unanswered
from app.models import Answer, Interview
from app.uow import UnitOfWork


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


class InterviewQuery:
    """Read-only queries and view-model helpers for interview sessions."""

    @staticmethod
    def get_interview(interview_id: str) -> Interview | None:
        """Retrieve an interview session by ID with answers loaded.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview with answers loaded, or None if not found.
        """
        with UnitOfWork() as uow:
            return uow.interviews.get(interview_id)

    @staticmethod
    def get_interview_or_raise(
        interview_id: str,
        *,
        uow: UnitOfWork | None = None,
    ) -> Interview:
        """Load an interview or raise ``InterviewNotFoundError``.

        When ``uow`` is provided, loads from that unit of work (same DB session).
        Otherwise opens a short-lived read-only ``UnitOfWork``.

        Args:
            interview_id: The session UUID.
            uow: Optional active unit of work for transactional loads.

        Returns:
            Interview with answers loaded.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
        """
        if uow is not None:
            interview = uow.interviews.get(interview_id)
        else:
            with UnitOfWork() as uow:
                interview = uow.interviews.get(interview_id)
        if not interview:
            raise InterviewNotFoundError(interview_id)
        return interview

    @staticmethod
    def get_current_unanswered(interview: Interview) -> Answer | None:
        """Return the first unanswered answer in display order.

        Args:
            interview: Interview with eager-loaded answers.

        Returns:
            The first Answer with ``answer_text IS NULL``, or None.
        """
        return find_first_unanswered(interview)

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
        """Build dashboard/interview page title from language.

        Args:
            interview: Interview instance.

        Returns:
            Title such as ``Python Interview``.
        """
        language = interview.language.replace("_", " ").replace("-", " ")
        return f"{language.title()} Interview"

    @staticmethod
    def list_dashboard_rows(limit: int = 20) -> list[DashboardInterviewRow]:
        """Load recent interviews for the dashboard history table.

        Args:
            limit: Maximum rows to return.

        Returns:
            Rows sorted newest-first (completed or started time).
        """
        with UnitOfWork() as uow:
            interviews = uow.interviews.list_recent(limit=limit)

        rows: list[DashboardInterviewRow] = []
        for interview in interviews:
            if interview.status == "completed":
                feedback = InterviewQuery.parse_overall_feedback(interview)
                breakdown = feedback.get("score_breakdown") if feedback else None
                max_score = InterviewQuery.compute_max_score(interview, breakdown)
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
                    title=InterviewQuery.interview_display_title(interview),
                    question_count=interview.question_count,
                    score_display=score_display,
                    status=interview.status,
                    status_label=status_label,
                    datetime_display=InterviewQuery.format_local_datetime(when),
                    url=f"/interview/{interview.id}",
                )
            )
        return rows
