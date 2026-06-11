# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview aggregate entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from app.interview.domain.exceptions import InterviewNotActiveError
from app.interview.domain.value_objects import SessionMode, SessionSelection

InterviewStatus = Literal["active", "completed"]


@dataclass(frozen=True, slots=True)
class Interview:
    """Interview session shell aggregate root.

    Attributes:
        id: Interview UUID.
        locale: Language code for feedback and voice.
        session_mode: Session mode (theory-only or multi-section order).
        selection: Parsed session selection (theory and coding branches).
        status: Session status (``active`` or ``completed``).
        overall_feedback: Parsed overall evaluation payload when completed.
        started_at: When the session began.
        completed_at: When the session ended, or None while active.
    """

    id: str
    locale: str
    session_mode: SessionMode
    selection: SessionSelection
    status: InterviewStatus
    overall_feedback: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def start_shell(
        cls,
        interview_id: str,
        *,
        selection: SessionSelection,
        locale: str,
        started_at: datetime | None = None,
    ) -> Interview:
        """Build a new active interview shell without section tasks.

        Args:
            interview_id: New session UUID.
            selection: Full session selection from setup.
            locale: Locale for AI feedback and follow-ups.
            started_at: Session start time (defaults to UTC now).

        Returns:
            Active shell aggregate.
        """
        when = started_at or datetime.now(UTC)
        return cls(
            id=interview_id,
            locale=locale,
            session_mode=selection.session_mode,
            selection=selection,
            status="active",
            overall_feedback=None,
            started_at=when,
            completed_at=None,
        )

    def ensure_active(self) -> None:
        """Ensure this interview accepts new section activity.

        Raises:
            InterviewNotActiveError: If the interview is not in ``active`` status.
        """
        if self.status != "active":
            raise InterviewNotActiveError(self.id)

    def with_session_completed(
        self,
        overall_feedback: dict[str, Any],
        *,
        completed_at: datetime | None = None,
    ) -> Interview:
        """Return shell marked completed with final evaluation payload.

        Args:
            overall_feedback: Parsed overall evaluation dict for persistence.
            completed_at: Session end time (defaults to UTC now).

        Returns:
            A new shell with ``status`` completed and feedback set.
        """
        when = completed_at or datetime.now(UTC)
        return replace(
            self,
            status="completed",
            overall_feedback=overall_feedback,
            completed_at=when,
        )
