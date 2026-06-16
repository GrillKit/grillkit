# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session creation service."""

import logging
from uuid import uuid4

from app.coding.domain.entities import CodingSectionStatus
from app.coding.services.creation import CodingSectionCreationService
from app.coding.services.planning import build_coding_task_plan
from app.interview.domain.entities import Interview
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.domain.value_objects import SessionMode, SessionSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.services.known_questions import KnownQuestionsService
from app.interview.services.read_model import load_interview_read
from app.interview.services.sections import (
    is_first_user_facing_section,
    phase_order_for_mode,
)
from app.shared.locales import normalize_locale
from app.theory.services.creation import TheorySectionCreationService

logger = logging.getLogger(__name__)


def _initial_coding_status(session_mode: SessionMode) -> CodingSectionStatus:
    """Return the initial coding section status for a session mode.

    Args:
        session_mode: Session mode from setup.

    Returns:
        ``active`` when coding is the first user-facing phase, else ``pending``.
    """
    order = phase_order_for_mode(session_mode)
    return "active" if order and order[0] == "coding" else "pending"


class SessionCreationService:
    """Orchestrates interview shell and section creation."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    def create_session(
        self,
        session: SessionSelection,
        locale: str = "en",
    ) -> InterviewRead:
        """Create a new interview session from a v2 session selection.

        Persists an interview shell and enabled section rows atomically in one
        transaction.

        Args:
            session: Full session selection from setup (v2).
            locale: Locale for AI feedback and follow-ups (default: "en").

        Returns:
            Read model for the created session with answers pre-populated.

        Raises:
            ValueError: If validation fails or no questions are available.
        """
        locale = normalize_locale(locale)

        interview_id = str(uuid4())
        shell = Interview.start_shell(
            interview_id,
            selection=session,
            locale=locale,
        )

        known_service = KnownQuestionsService(self._uow)
        theory_excluded = (
            known_service.list_ids("theory")
            if session.exclude_known and session.theory.enabled
            else frozenset()
        )
        coding_excluded = (
            known_service.list_ids("coding")
            if session.exclude_known and session.coding.enabled
            else frozenset()
        )

        self._uow.interviews.create_shell(shell)
        if session.theory.enabled:
            TheorySectionCreationService(self._uow).create(
                interview_id,
                selection=session.theory_selection,
                locale=locale,
                question_count=session.theory.question_count,
                task_time_limit_seconds=session.theory.task_time_limit_seconds,
                start_first_task_timer=is_first_user_facing_section(
                    session.session_mode,
                    "theory",
                ),
                excluded_ids=theory_excluded,
            )
        if session.coding.enabled:
            planned_tasks = build_coding_task_plan(
                session.coding_selection,
                session.coding.question_count,
                locale=locale,
                excluded_ids=coding_excluded,
            )
            CodingSectionCreationService(self._uow).create(
                interview_id,
                selection=session.coding_selection,
                locale=locale,
                planned_tasks=planned_tasks,
                task_time_limit_seconds=session.coding.task_time_limit_seconds,
                status=_initial_coding_status(session.session_mode),
            )
        read_model = load_interview_read(self._uow, interview_id)
        if read_model is None:
            raise InterviewNotFoundError(interview_id)
        return read_model
