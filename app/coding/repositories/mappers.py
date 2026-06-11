# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""ORM ↔ domain ↔ read-model mappers for coding persistence."""

from __future__ import annotations

import json
from typing import Any

from app.coding.domain.entities import CodeRunAttempt as DomainCodeRunAttempt
from app.coding.domain.entities import CodingSection as DomainCodingSection
from app.coding.domain.entities import CodingSectionStatus
from app.coding.domain.entities import CodingTask as DomainCodingTask
from app.coding.domain.value_objects import RunOutcomeStatus
from app.coding.schemas.coding import CodingSectionRead, CodingTaskRead
from app.interview.domain.serialization import (
    parse_coding_selection_spec,
    parse_overall_feedback,
    selection_to_spec,
)
from app.shared.infrastructure.models import CodeRunAttempt as OrmCodeRunAttempt
from app.shared.infrastructure.models import CodingSection as OrmCodingSection
from app.shared.infrastructure.models import CodingTask as OrmCodingTask


def _task_ids_from_tasks(tasks: tuple[DomainCodingTask, ...]) -> tuple[str, ...]:
    """Derive ordered task IDs from initial task rounds.

    Args:
        tasks: Coding tasks for a section.

    Returns:
        Task IDs for round 0 rows sorted by display order.
    """
    initial = sorted(
        (task for task in tasks if task.round == 0),
        key=lambda task: task.order,
    )
    return tuple(task.task_id for task in initial)


def _parse_task_spec(raw: str) -> dict[str, Any]:
    """Parse persisted task spec JSON.

    Args:
        raw: JSON string from ``coding_tasks.task_spec``.

    Returns:
        Parsed dict, or empty dict when invalid.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_optional_json(raw: str | None) -> dict[str, Any] | None:
    """Parse optional JSON column value.

    Args:
        raw: JSON string or None.

    Returns:
        Parsed dict, or None when unset or invalid.
    """
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def coding_task_from_orm(
    row: OrmCodingTask,
    *,
    interview_id: str,
) -> DomainCodingTask:
    """Map an ORM coding task row to a domain entity.

    Args:
        row: SQLAlchemy CodingTask linked to a coding section.
        interview_id: Parent interview UUID from the coding section.

    Returns:
        Immutable domain CodingTask.
    """
    return DomainCodingTask(
        id=row.id,
        coding_section_id=row.coding_section_id,
        interview_id=interview_id,
        task_id=row.task_id,
        order=row.order,
        round=row.round,
        prompt_text=row.prompt_text,
        task_spec=_parse_task_spec(row.task_spec),
        submitted_code=row.submitted_code,
        submit_test_summary=_parse_optional_json(row.submit_test_summary),
        score=row.score,
        feedback=row.feedback,
        started_at=row.started_at,
        created_at=row.created_at,
    )


def domain_coding_task_to_orm(
    task: DomainCodingTask,
    *,
    coding_section_id: int | None = None,
) -> OrmCodingTask:
    """Map a domain coding task to a new ORM row.

    Args:
        task: Domain coding task (typically ``id`` is ``CodingTask.NEW_ID``).
        coding_section_id: Parent section ID override when inserting.

    Returns:
        Detached ORM CodingTask ready to be added to a session.
    """
    section_id = (
        coding_section_id if coding_section_id is not None else task.coding_section_id
    )
    return OrmCodingTask(
        coding_section_id=section_id,
        task_id=task.task_id,
        order=task.order,
        round=task.round,
        prompt_text=task.prompt_text,
        task_spec=json.dumps(task.task_spec, separators=(",", ":")),
        submitted_code=task.submitted_code,
        submit_test_summary=(
            json.dumps(task.submit_test_summary, separators=(",", ":"))
            if task.submit_test_summary is not None
            else None
        ),
        score=task.score,
        feedback=task.feedback,
        started_at=task.started_at,
        created_at=task.created_at,
    )


def coding_section_from_orm(section: OrmCodingSection) -> DomainCodingSection:
    """Map an ORM coding section row to a domain aggregate.

    Args:
        section: SQLAlchemy CodingSection with tasks loaded.

    Returns:
        Immutable domain CodingSection including tasks.
    """
    status: CodingSectionStatus
    if section.status == "completed":
        status = "completed"
    elif section.status == "skipped":
        status = "skipped"
    elif section.status == "pending":
        status = "pending"
    else:
        status = "active"
    tasks = tuple(
        coding_task_from_orm(row, interview_id=section.interview_id)
        for row in section.tasks
    )
    return DomainCodingSection(
        id=section.id,
        interview_id=section.interview_id,
        locale=section.locale or "en",
        selection=parse_coding_selection_spec(section.selection_spec),
        task_count=section.task_count or 0,
        task_ids=_task_ids_from_tasks(tasks),
        task_time_limit_seconds=section.task_time_limit_seconds,
        status=status,
        section_score=section.section_score,
        section_feedback=parse_overall_feedback(section.section_feedback),
        tasks=tasks,
    )


def coding_section_to_orm(section: DomainCodingSection) -> OrmCodingSection:
    """Map a new domain coding section to a detached ORM row.

    Args:
        section: Domain section from ``CodingSection.start``.

    Returns:
        ORM CodingSection ready for ``session.add``.
    """
    fields: dict[str, Any] = {
        "interview_id": section.interview_id,
        "selection_spec": selection_to_spec(section.selection),
        "task_count": section.task_count,
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
    if section.id != DomainCodingSection.NEW_ID:
        fields["id"] = section.id
    return OrmCodingSection(**fields)


def coding_section_to_orm_fields(section: DomainCodingSection) -> dict[str, Any]:
    """Extract ORM-mutable coding section fields from a domain aggregate.

    Args:
        section: Domain coding section aggregate.

    Returns:
        Dict of column names to values for partial ORM updates.
    """
    return {
        "selection_spec": selection_to_spec(section.selection),
        "task_count": section.task_count,
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


def _parse_test_results(raw: str | None) -> tuple[dict[str, Any], ...]:
    """Parse persisted per-test JSON payloads.

    Args:
        raw: JSON array stored on ``code_run_attempts.test_results``.

    Returns:
        Tuple of test result dicts.
    """
    if raw is None:
        return ()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(item for item in data if isinstance(item, dict))


def code_run_attempt_from_orm(row: OrmCodeRunAttempt) -> DomainCodeRunAttempt:
    """Map an ORM run attempt row to a domain entity.

    Args:
        row: SQLAlchemy CodeRunAttempt row.

    Returns:
        Immutable domain CodeRunAttempt.
    """
    status: RunOutcomeStatus = row.status  # type: ignore[assignment]
    return DomainCodeRunAttempt(
        id=row.id,
        coding_task_id=row.coding_task_id,
        attempt_no=row.attempt_no or 0,
        source_code=row.source_code,
        language=row.language,
        status=status,
        stdout=row.stdout,
        stderr=row.stderr,
        compile_output=row.compile_output,
        tests_passed=row.tests_passed or 0,
        tests_total=row.tests_total or 0,
        test_results=_parse_test_results(row.test_results),
        duration_ms=row.duration_ms,
        created_at=row.created_at,
    )


def domain_code_run_attempt_to_orm(
    attempt: DomainCodeRunAttempt,
) -> OrmCodeRunAttempt:
    """Map a domain run attempt to a new ORM row.

    Args:
        attempt: Domain attempt to persist.

    Returns:
        Detached ORM row ready for ``session.add``.
    """
    return OrmCodeRunAttempt(
        coding_task_id=attempt.coding_task_id,
        attempt_no=attempt.attempt_no,
        source_code=attempt.source_code,
        language=attempt.language,
        status=attempt.status,
        stdout=attempt.stdout,
        stderr=attempt.stderr,
        compile_output=attempt.compile_output,
        tests_passed=attempt.tests_passed,
        tests_total=attempt.tests_total,
        test_results=json.dumps(list(attempt.test_results), separators=(",", ":")),
        duration_ms=attempt.duration_ms,
        created_at=attempt.created_at,
    )


def coding_task_read_from_domain(task: DomainCodingTask) -> CodingTaskRead:
    """Map a domain coding task to a read model.

    Args:
        task: Domain coding task entity.

    Returns:
        Immutable CodingTaskRead for services and API.
    """
    return CodingTaskRead(
        id=task.id,
        task_id=task.task_id,
        order=task.order,
        round=task.round,
        prompt_text=task.prompt_text,
        task_spec=dict(task.task_spec),
        submitted_code=task.submitted_code,
        score=task.score,
        feedback=task.feedback,
        started_at=task.started_at,
    )


def coding_section_to_read(section: DomainCodingSection) -> CodingSectionRead:
    """Map a domain coding section to a read model.

    Args:
        section: Domain coding section aggregate.

    Returns:
        Immutable CodingSectionRead for services and API.
    """
    return CodingSectionRead(
        id=section.id,
        interview_id=section.interview_id,
        status=section.status,
        locale=section.locale,
        selection_spec=selection_to_spec(section.selection),
        task_count=section.task_count,
        task_time_limit_seconds=section.task_time_limit_seconds,
        tasks=[coding_task_read_from_domain(task) for task in section.tasks],
        section_score=section.section_score,
        section_feedback=section.section_feedback,
    )
