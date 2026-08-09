# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for session creation."""

from app.coding.use_cases.create_section import CreateCodingSection
from app.interview.domain.value_objects import SessionSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.use_cases.create_session import CreateInterviewSession
from app.theory.use_cases.create_section import CreateTheorySection


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
        service = CreateInterviewSession(
            uow,
            create_theory_section=CreateTheorySection(uow),
            create_coding_section=CreateCodingSection(uow),
        )
        return service.create_session(session, locale=locale)
