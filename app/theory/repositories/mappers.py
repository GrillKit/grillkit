# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""ORM ↔ domain ↔ read-model mappers for theory persistence."""

from __future__ import annotations

import json
from typing import Any

from app.interview.domain.serialization import (
    parse_overall_feedback,
    parse_selection_spec,
    selection_to_spec,
)
from app.shared.infrastructure.models import Answer as OrmAnswer
from app.shared.infrastructure.models import TheorySection as OrmTheorySection
from app.theory.domain.entities import TheorySection as DomainTheorySection
from app.theory.domain.entities import TheorySectionStatus
from app.theory.domain.entities import TheoryTask as DomainTheoryTask
from app.theory.schemas.theory import TheoryTaskRead


def _expected_points_to_json(points: tuple[str, ...]) -> str | None:
    """Serialize rubric bullets for ORM storage.

    Args:
        points: Domain rubric tuple.

    Returns:
        JSON array string, or None when empty.
    """
    if not points:
        return None
    return json.dumps(list(points), separators=(",", ":"))


def _expected_points_from_json(raw: str | None) -> tuple[str, ...]:
    """Deserialize rubric bullets from an ORM column.

    Args:
        raw: JSON array string or None for legacy rows.

    Returns:
        Tuple of rubric bullet strings.
    """
    if raw is None:
        return ()
    data = json.loads(raw)
    if not isinstance(data, list):
        return ()
    return tuple(str(point) for point in data)


def _question_ids_from_tasks(tasks: tuple[DomainTheoryTask, ...]) -> tuple[str, ...]:
    """Derive ordered question IDs from initial task rounds.

    Args:
        tasks: Theory tasks for a section.

    Returns:
        Question IDs for round 0 tasks sorted by display order.
    """
    initial = sorted(
        (task for task in tasks if task.round == 0),
        key=lambda task: task.order,
    )
    return tuple(task.question_id for task in initial)


def theory_task_from_orm(
    answer: OrmAnswer,
    *,
    interview_id: str,
) -> DomainTheoryTask:
    """Map an ORM answer row to a domain theory task.

    Args:
        answer: SQLAlchemy Answer linked to a theory section.
        interview_id: Parent interview UUID from the theory section.

    Returns:
        Immutable domain TheoryTask.
    """
    return DomainTheoryTask(
        id=answer.id,
        theory_section_id=answer.theory_section_id,
        interview_id=interview_id,
        question_id=answer.question_id,
        order=answer.order,
        round=answer.round,
        question_text=answer.question_text,
        question_code=answer.question_code,
        expected_points=_expected_points_from_json(answer.expected_points),
        answer_text=answer.answer_text,
        score=answer.score,
        feedback=answer.feedback,
        started_at=answer.started_at,
        created_at=answer.created_at,
    )


def domain_theory_task_to_orm(
    task: DomainTheoryTask,
    *,
    theory_section_id: int | None = None,
) -> OrmAnswer:
    """Map a domain theory task to a new ORM answer row.

    Args:
        task: Domain theory task (typically ``id`` is ``TheoryTask.NEW_ID``).
        theory_section_id: Parent section ID override when inserting.

    Returns:
        Detached ORM Answer ready to be added to a session.
    """
    section_id = (
        theory_section_id if theory_section_id is not None else task.theory_section_id
    )
    return OrmAnswer(
        theory_section_id=section_id,
        question_id=task.question_id,
        order=task.order,
        round=task.round,
        question_text=task.question_text,
        question_code=task.question_code,
        expected_points=_expected_points_to_json(task.expected_points),
        answer_text=task.answer_text,
        score=task.score,
        feedback=task.feedback,
        started_at=task.started_at,
        created_at=task.created_at,
    )


def theory_section_from_orm(section: OrmTheorySection) -> DomainTheorySection:
    """Map an ORM theory section row to a domain aggregate.

    Args:
        section: SQLAlchemy TheorySection with tasks loaded.

    Returns:
        Immutable domain TheorySection including tasks.
    """
    status: TheorySectionStatus
    if section.status == "completed":
        status = "completed"
    elif section.status == "skipped":
        status = "skipped"
    else:
        status = "active"
    tasks = tuple(
        theory_task_from_orm(answer, interview_id=section.interview_id)
        for answer in section.tasks
    )
    return DomainTheorySection(
        id=section.id,
        interview_id=section.interview_id,
        locale=section.locale or "en",
        selection=parse_selection_spec(section.selection_spec),
        question_count=section.question_count or 0,
        question_ids=_question_ids_from_tasks(tasks),
        task_time_limit_seconds=section.task_time_limit_seconds,
        status=status,
        section_score=section.section_score,
        section_feedback=parse_overall_feedback(section.section_feedback),
        tasks=tasks,
    )


def theory_section_to_orm(section: DomainTheorySection) -> OrmTheorySection:
    """Map a new domain theory section to a detached ORM row.

    Args:
        section: Domain section from ``TheorySection.start``.

    Returns:
        ORM TheorySection ready for ``session.add``.
    """
    fields: dict[str, Any] = {
        "interview_id": section.interview_id,
        "selection_spec": selection_to_spec(section.selection),
        "question_count": section.question_count,
        "task_time_limit_seconds": section.task_time_limit_seconds,
        "status": section.status,
        "section_score": section.section_score,
        "section_feedback": (
            json.dumps(section.section_feedback, separators=(",", ":"))
            if section.section_feedback is not None
            else None
        ),
        "locale": section.locale,
    }
    if section.id != DomainTheorySection.NEW_ID:
        fields["id"] = section.id
    return OrmTheorySection(**fields)


def theory_section_to_orm_fields(section: DomainTheorySection) -> dict[str, Any]:
    """Extract ORM-mutable theory section fields from a domain aggregate.

    Args:
        section: Domain theory section aggregate.

    Returns:
        Dict of column names to values for partial ORM updates.
    """
    return {
        "selection_spec": selection_to_spec(section.selection),
        "question_count": section.question_count,
        "task_time_limit_seconds": section.task_time_limit_seconds,
        "status": section.status,
        "section_score": section.section_score,
        "section_feedback": (
            json.dumps(section.section_feedback, separators=(",", ":"))
            if section.section_feedback is not None
            else None
        ),
        "locale": section.locale,
    }


def theory_task_read_from_domain(task: DomainTheoryTask) -> TheoryTaskRead:
    """Map a domain theory task to a read model.

    Args:
        task: Domain theory task entity.

    Returns:
        Immutable TheoryTaskRead for services and API.
    """
    return TheoryTaskRead(
        id=task.id,
        question_id=task.question_id,
        order=task.order,
        round=task.round,
        question_text=task.question_text,
        question_code=task.question_code,
        answer_text=task.answer_text,
        score=task.score,
        feedback=task.feedback,
        started_at=task.started_at,
    )
