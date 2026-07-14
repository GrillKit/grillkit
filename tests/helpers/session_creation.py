# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for session creation."""

from app.interview.domain.value_objects import SessionSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.services.creation import SessionCreationService


def create_session(
    session: SessionSelection,
    *,
    locale: str = "en",
) -> InterviewRead:
    """Create a session inside an auto-commit application UoW.

    Args:
        session: Full session selection from setup.
        locale: Locale for AI feedback and follow-ups.

    Returns:
        Read model for the created session.
    """
    with InterviewUnitOfWork(auto_commit=True) as uow:
        return SessionCreationService(uow).create_session(session, locale=locale)
