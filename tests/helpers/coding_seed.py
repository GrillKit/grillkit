# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding coding sections linked to interview rows."""

import json

from sqlalchemy.orm import Session

from app.interview.domain.serialization import selection_to_spec, session_to_spec
from app.interview.domain.value_objects import (
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import CodingSection, CodingTask, Interview


def create_coding_section_for_interview(
    db_session: Session,
    interview: Interview,
    *,
    task_count: int = 2,
    task_time_limit_seconds: int | None = None,
    status: str = "active",
    selection_spec: str | None = None,
) -> CodingSection:
    """Insert a coding section row matching an interview shell.

    Args:
        db_session: Active SQLAlchemy session.
        interview: Parent interview ORM row (must be flushed).
        task_count: Number of coding tasks in the section.
        task_time_limit_seconds: Optional per-task timer in seconds.
        status: Section status to persist.
        selection_spec: Optional coding-specific selection spec; defaults to interview.selection_spec.

    Returns:
        Persisted coding section with assigned primary key.
    """
    section = CodingSection(
        interview_id=interview.id,
        selection_spec=selection_spec if selection_spec is not None else interview.selection_spec,
        task_count=task_count,
        task_time_limit_seconds=task_time_limit_seconds,
        locale=interview.locale or "en",
        status=status,
    )
    db_session.add(section)
    db_session.flush()
    return section


def attach_coding_tasks(
    db_session: Session,
    section: CodingSection,
    *,
    task_ids: list[str] | None = None,
) -> list[CodingTask]:
    """Create coding task rows for a section.

    Args:
        db_session: Active SQLAlchemy session.
        section: Parent coding section ORM row (must be flushed).
        task_ids: Task IDs to create; defaults to two placeholder tasks.

    Returns:
        Persisted coding task rows.
    """
    ids = task_ids or ["cod-001", "cod-002"]
    tasks: list[CodingTask] = []
    for order, task_id in enumerate(ids, start=1):
        task = CodingTask(
            coding_section_id=section.id,
            task_id=task_id,
            order=order,
            round=0,
            prompt_text=f"Task {task_id}",
            task_spec=json.dumps(
                {
                    "language": "python",
                    "evaluation_mode": "ai",
                    "starter_code": "pass",
                }
            ),
        )
        db_session.add(task)
        tasks.append(task)
    db_session.flush()
    return tasks


def seed_active_coding_interview(
    interview_id: str = "coding-api-1",
    *,
    task_ids: list[str] | None = None,
) -> tuple[str, str]:
    """Persist an active interview shell with one coding section and tasks.

    Args:
        interview_id: Interview primary key.
        task_ids: Coding bank task IDs to attach.

    Returns:
        Tuple of interview id and the first task's YAML task id.
    """
    ids = task_ids or ["cod-001"]
    session = SessionSelection(
        session_mode="coding_only",
        theory=SectionBranchSpec(
            enabled=False,
            question_count=0,
            task_time_limit_seconds=None,
            sources=(),
        ),
        coding=SectionBranchSpec(
            enabled=True,
            question_count=len(ids),
            task_time_limit_seconds=None,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
        ),
    )
    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            locale="en",
            selection_spec=session_to_spec(session),
            session_mode="coding_only",
            status="active",
        )
        uow.interviews.add(interview)
        uow.flush()
        section = create_coding_section_for_interview(
            uow.session,
            interview,
            task_count=len(ids),
            status="active",
        )
        section.selection_spec = selection_to_spec(session.coding_selection)
        attach_coding_tasks(uow.session, section, task_ids=ids)
        first_task_id = ids[0]
    return interview_id, first_task_id
