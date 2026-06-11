# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding theory sections linked to interview rows."""

from sqlalchemy.orm import Session

from app.shared.infrastructure.models import Answer, Interview, TheorySection


def create_theory_section_for_interview(
    db_session: Session,
    interview: Interview,
    *,
    question_count: int = 5,
    task_time_limit_seconds: int | None = None,
    status: str = "active",
) -> TheorySection:
    """Insert a theory section row matching an interview shell.

    Args:
        db_session: Active SQLAlchemy session.
        interview: Parent interview ORM row (must be flushed).
        question_count: Number of theory questions in the section.
        task_time_limit_seconds: Optional per-task timer in seconds.
        status: Section status to persist.

    Returns:
        Persisted theory section with assigned primary key.
    """
    section = TheorySection(
        interview_id=interview.id,
        selection_spec=interview.selection_spec,
        question_count=question_count,
        task_time_limit_seconds=task_time_limit_seconds,
        locale=interview.locale or "en",
        status=status,
    )
    db_session.add(section)
    db_session.flush()
    return section


def attach_theory_section_to_answers(
    db_session: Session,
    interview: Interview,
    answers: list[Answer],
    *,
    question_count: int | None = None,
    task_time_limit_seconds: int | None = None,
    status: str = "active",
) -> TheorySection:
    """Create a theory section and link answer rows to it.

    Args:
        db_session: Active SQLAlchemy session.
        interview: Parent interview ORM row (must be flushed).
        answers: Answer rows to link via ``theory_section_id``.
        question_count: Section question count; defaults to answer list length.
        task_time_limit_seconds: Optional per-task timer in seconds.
        status: Section status to persist.

    Returns:
        Persisted theory section with answers linked.
    """
    resolved_count = question_count if question_count is not None else len(answers)
    section = create_theory_section_for_interview(
        db_session,
        interview,
        question_count=resolved_count,
        task_time_limit_seconds=task_time_limit_seconds,
        status=status,
    )
    for answer in answers:
        answer.theory_section_id = section.id
        db_session.add(answer)
    db_session.flush()
    return section
