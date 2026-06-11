# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""ORM ↔ domain ↔ read-model mappers for interview persistence."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.coding.domain.entities import CodingSection as DomainCodingSection
from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.entities import InterviewStatus
from app.interview.domain.serialization import (
    parse_overall_feedback,
    parse_session_spec,
    session_to_spec,
)
from app.interview.schemas.interview import InterviewRead
from app.interview.services.scoring import (
    completed_score_fallback,
    score_from_overall_feedback,
)
from app.shared.infrastructure.models import Interview as OrmInterview
from app.theory.domain.entities import TheorySection as DomainTheorySection
from app.theory.repositories.mappers import (
    theory_section_from_orm,
    theory_task_read_from_domain,
)

_EPOCH = datetime.min.replace(tzinfo=UTC)


def _question_ids_to_json(question_ids: tuple[str, ...]) -> str:
    """Serialize question IDs for persistence.

    Args:
        question_ids: Question IDs in display order.

    Returns:
        JSON array string.
    """
    return json.dumps(list(question_ids), separators=(",", ":"))


def _resolve_completed_score(
    shell: DomainInterview,
    theory: DomainTheorySection | None,
    coding: DomainCodingSection | None,
) -> int | None:
    """Resolve display score for a completed session read model.

    Args:
        shell: Interview shell aggregate.
        theory: Theory section aggregate, if present.
        coding: Coding section aggregate, if present.

    Returns:
        Display score from feedback or section totals, or None while active.
    """
    if shell.status != "completed":
        return None
    score = score_from_overall_feedback(shell.overall_feedback)
    if score is not None:
        return score
    return completed_score_fallback(shell, theory, coding)


def interview_shell_from_orm(interview: OrmInterview) -> DomainInterview:
    """Map an ORM interview row to a shell domain aggregate.

    Args:
        interview: SQLAlchemy Interview row.

    Returns:
        Immutable interview shell without section tasks.
    """
    status: InterviewStatus = (
        "completed" if interview.status == "completed" else "active"
    )
    return DomainInterview(
        id=interview.id,
        locale=interview.locale or "en",
        session_mode=interview.session_mode,  # type: ignore[arg-type]
        selection=parse_session_spec(interview.selection_spec),
        status=status,
        overall_feedback=parse_overall_feedback(interview.overall_feedback),
        started_at=interview.started_at,
        completed_at=interview.completed_at,
    )


def compose_interview_read(
    shell: DomainInterview,
    theory: DomainTheorySection | None,
    coding: DomainCodingSection | None = None,
) -> InterviewRead:
    """Compose an interview read model from shell and optional section aggregates.

    Args:
        shell: Interview shell aggregate.
        theory: Theory section aggregate with tasks, if present.
        coding: Coding section aggregate, used for coding-only score fallback.

    Returns:
        Immutable InterviewRead for services, API, and templates.
    """
    score = _resolve_completed_score(shell, theory, coding)

    if theory is None:
        return InterviewRead(
            id=shell.id,
            status=shell.status,
            locale=shell.locale,
            selection_spec=session_to_spec(shell.selection),
            question_ids="[]",
            question_count=0,
            question_time_limit_seconds=None,
            answers=[],
            score=score,
            overall_feedback=shell.overall_feedback,
            started_at=shell.started_at,
            completed_at=shell.completed_at,
        )

    answers = [theory_task_read_from_domain(task) for task in theory.tasks]

    return InterviewRead(
        id=shell.id,
        status=shell.status,
        locale=theory.locale,
        selection_spec=session_to_spec(shell.selection),
        question_ids=_question_ids_to_json(theory.question_ids),
        question_count=theory.question_count,
        question_time_limit_seconds=theory.task_time_limit_seconds,
        answers=answers,
        score=score,
        overall_feedback=shell.overall_feedback,
        started_at=shell.started_at,
        completed_at=shell.completed_at,
    )


def interview_from_orm(interview: OrmInterview) -> DomainInterview:
    """Map an ORM interview row to a shell domain aggregate.

    Args:
        interview: SQLAlchemy Interview row.

    Returns:
        Interview shell aggregate.
    """
    return interview_shell_from_orm(interview)


def interview_read_from_orm(
    interview: OrmInterview,
    *,
    coding: DomainCodingSection | None = None,
) -> InterviewRead:
    """Map an ORM interview row and section aggregates to a read model.

    Args:
        interview: SQLAlchemy Interview with optional theory section loaded.
        coding: Coding section aggregate for coding-only score fallback.

    Returns:
        Composed interview read model.
    """
    shell = interview_shell_from_orm(interview)
    theory = (
        theory_section_from_orm(interview.theory_section)
        if interview.theory_section is not None
        else None
    )
    return compose_interview_read(shell, theory, coding)


def interview_to_read(interview: DomainInterview) -> InterviewRead:
    """Map a shell aggregate to a minimal read model without theory tasks.

    Prefer ``compose_interview_read`` when section data is available.

    Args:
        interview: Interview shell aggregate.

    Returns:
        Interview read model without answers.
    """
    return compose_interview_read(interview, None)


def interview_shell_to_orm(interview: DomainInterview) -> OrmInterview:
    """Map a new interview shell to a detached ORM row.

    Args:
        interview: Domain shell from ``Interview.start_shell``.

    Returns:
        ORM Interview without nested section rows.
    """
    return OrmInterview(
        id=interview.id,
        locale=interview.locale,
        selection_spec=session_to_spec(interview.selection),
        session_mode=interview.session_mode,
        status=interview.status,
        overall_feedback=(
            json.dumps(interview.overall_feedback, separators=(",", ":"))
            if interview.overall_feedback is not None
            else None
        ),
        started_at=interview.started_at,
        completed_at=interview.completed_at,
    )


def interview_to_orm_fields(interview: DomainInterview) -> dict[str, Any]:
    """Extract ORM-mutable interview shell fields from a domain aggregate.

    Args:
        interview: Domain interview shell aggregate.

    Returns:
        Dict of column names to values for partial ORM updates.
    """
    return {
        "locale": interview.locale,
        "selection_spec": session_to_spec(interview.selection),
        "session_mode": interview.session_mode,
        "status": interview.status,
        "overall_feedback": (
            json.dumps(interview.overall_feedback, separators=(",", ":"))
            if interview.overall_feedback is not None
            else None
        ),
        "started_at": interview.started_at,
        "completed_at": interview.completed_at,
    }
