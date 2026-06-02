# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""ORM ↔ domain ↔ read-model mappers for interview persistence."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.interview.domain.entities import Answer as DomainAnswer
from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.entities import InterviewStatus
from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.rules.feedback import parse_overall_feedback
from app.interview.services.rules.selection import (
    parse_selection_spec,
    selection_to_spec,
)
from app.shared.infrastructure.models import Answer as OrmAnswer
from app.shared.infrastructure.models import Interview as OrmInterview

_EPOCH = datetime.min.replace(tzinfo=UTC)


def _question_ids_from_json(raw: str) -> tuple[str, ...]:
    """Parse ``question_ids`` JSON into an ordered tuple.

    Args:
        raw: JSON array string from persistence.

    Returns:
        Question IDs in display order.
    """
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(str(item) for item in parsed)


def _question_ids_to_json(question_ids: tuple[str, ...]) -> str:
    """Serialize question IDs for persistence.

    Args:
        question_ids: Question IDs in display order.

    Returns:
        JSON array string.
    """
    return json.dumps(list(question_ids), separators=(",", ":"))


def domain_answer_to_orm(answer: DomainAnswer) -> OrmAnswer:
    """Map a domain answer to a new ORM row for insert.

    Args:
        answer: Domain answer (typically ``id`` is ``Answer.NEW_ID``).

    Returns:
        Detached ORM Answer ready to be added to a session.
    """
    return OrmAnswer(
        interview_id=answer.interview_id,
        question_id=answer.question_id,
        order=answer.order,
        round=answer.round,
        question_text=answer.question_text,
        question_code=answer.question_code,
        answer_text=answer.answer_text,
        score=answer.score,
        feedback=answer.feedback,
        started_at=answer.started_at,
        created_at=answer.created_at,
    )


def answer_from_orm(answer: OrmAnswer) -> DomainAnswer:
    """Map an ORM answer row to a domain answer.

    Args:
        answer: SQLAlchemy Answer instance.

    Returns:
        Immutable domain Answer.
    """
    return DomainAnswer(
        id=answer.id,
        interview_id=answer.interview_id,
        question_id=answer.question_id,
        order=answer.order,
        round=answer.round,
        question_text=answer.question_text,
        question_code=answer.question_code,
        answer_text=answer.answer_text,
        score=answer.score,
        feedback=answer.feedback,
        started_at=answer.started_at,
        created_at=answer.created_at,
    )


def answer_read_from_domain(answer: DomainAnswer) -> AnswerRead:
    """Map a domain answer to a read model.

    Args:
        answer: Domain answer entity.

    Returns:
        Immutable AnswerRead for services and API.
    """
    return AnswerRead(
        id=answer.id,
        question_id=answer.question_id,
        order=answer.order,
        round=answer.round,
        question_text=answer.question_text,
        question_code=answer.question_code,
        answer_text=answer.answer_text,
        score=answer.score,
        feedback=answer.feedback,
        started_at=answer.started_at,
    )


def answer_read_to_domain(answer: AnswerRead, interview_id: str) -> DomainAnswer:
    """Map a read-model answer into a domain answer for rule evaluation.

    Args:
        answer: Answer read snapshot.
        interview_id: Parent interview UUID.

    Returns:
        Domain answer with a placeholder ``created_at`` when unknown.
    """
    created_at = answer.started_at if answer.started_at is not None else _EPOCH
    return DomainAnswer(
        id=answer.id,
        interview_id=interview_id,
        question_id=answer.question_id,
        order=answer.order,
        round=answer.round,
        question_text=answer.question_text,
        question_code=answer.question_code,
        answer_text=answer.answer_text,
        score=answer.score,
        feedback=answer.feedback,
        started_at=answer.started_at,
        created_at=created_at,
    )


def interview_from_orm(interview: OrmInterview) -> DomainInterview:
    """Map an ORM interview row to a domain aggregate.

    Args:
        interview: SQLAlchemy Interview with answers loaded.

    Returns:
        Immutable domain Interview.
    """
    status: InterviewStatus = (
        "completed" if interview.status == "completed" else "active"
    )
    return DomainInterview(
        id=interview.id,
        locale=interview.locale or "en",
        selection=parse_selection_spec(interview.selection_spec),
        question_count=interview.question_count or 0,
        question_ids=_question_ids_from_json(interview.question_ids or "[]"),
        question_time_limit_seconds=interview.question_time_limit_seconds,
        status=status,
        score=interview.score,
        overall_feedback=parse_overall_feedback(interview.overall_feedback),
        started_at=interview.started_at,
        completed_at=interview.completed_at,
        answers=tuple(answer_from_orm(a) for a in interview.answers),
    )


def interview_read_to_domain(interview: InterviewRead) -> DomainInterview:
    """Map an interview read model to a domain aggregate for rules.

    Args:
        interview: Interview read snapshot with answers.

    Returns:
        Domain interview aggregate.
    """
    status: InterviewStatus = (
        "completed" if interview.status == "completed" else "active"
    )
    return DomainInterview(
        id=interview.id,
        locale=interview.locale,
        selection=parse_selection_spec(interview.selection_spec),
        question_count=interview.question_count,
        question_ids=_question_ids_from_json(interview.question_ids),
        question_time_limit_seconds=interview.question_time_limit_seconds,
        status=status,
        score=interview.score,
        overall_feedback=interview.overall_feedback,
        started_at=interview.started_at or _EPOCH,
        completed_at=interview.completed_at,
        answers=tuple(
            answer_read_to_domain(answer, interview.id) for answer in interview.answers
        ),
    )


def interview_to_read(interview: DomainInterview) -> InterviewRead:
    """Map a domain aggregate to a read model.

    Args:
        interview: Domain interview aggregate.

    Returns:
        Immutable InterviewRead for services and API.
    """
    return InterviewRead(
        id=interview.id,
        status=interview.status,
        locale=interview.locale,
        selection_spec=selection_to_spec(interview.selection),
        question_ids=_question_ids_to_json(interview.question_ids),
        question_count=interview.question_count,
        question_time_limit_seconds=interview.question_time_limit_seconds,
        answers=[answer_read_from_domain(a) for a in interview.answers],
        score=interview.score,
        overall_feedback=interview.overall_feedback,
        started_at=interview.started_at,
        completed_at=interview.completed_at,
    )


def interview_to_orm(interview: DomainInterview) -> OrmInterview:
    """Map a new domain aggregate to a detached ORM interview row.

    Args:
        interview: Domain aggregate from ``Interview.start``.

    Returns:
        ORM Interview with nested answer rows ready for ``session.add``.
    """
    orm_interview = OrmInterview(
        id=interview.id,
        locale=interview.locale,
        selection_spec=selection_to_spec(interview.selection),
        question_count=interview.question_count,
        question_ids=_question_ids_to_json(interview.question_ids),
        question_time_limit_seconds=interview.question_time_limit_seconds,
        status=interview.status,
        score=interview.score,
        overall_feedback=None,
        started_at=interview.started_at,
        completed_at=interview.completed_at,
    )
    orm_interview.answers = [
        domain_answer_to_orm(answer) for answer in interview.answers
    ]
    return orm_interview


def interview_to_orm_fields(interview: DomainInterview) -> dict[str, Any]:
    """Extract ORM-mutable interview fields from a domain aggregate.

    Args:
        interview: Domain interview aggregate.

    Returns:
        Dict of column names to values for partial ORM updates.
    """
    return {
        "locale": interview.locale,
        "selection_spec": selection_to_spec(interview.selection),
        "question_count": interview.question_count,
        "question_ids": _question_ids_to_json(interview.question_ids),
        "question_time_limit_seconds": interview.question_time_limit_seconds,
        "status": interview.status,
        "score": interview.score,
        "overall_feedback": (
            json.dumps(interview.overall_feedback, separators=(",", ":"))
            if interview.overall_feedback is not None
            else None
        ),
        "started_at": interview.started_at,
        "completed_at": interview.completed_at,
    }
