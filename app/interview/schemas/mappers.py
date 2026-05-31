# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""ORM to Pydantic read-model mappers for interview sessions."""

import json
from typing import Any

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.shared.infrastructure.models import Answer, Interview


def _parse_overall_feedback(raw: str | None) -> dict[str, Any] | None:
    """Parse ``overall_feedback`` JSON from the database.

    Args:
        raw: JSON string stored on the interview row.

    Returns:
        Parsed dict, or None if the session has no feedback.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"overall_feedback": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"overall_feedback": raw}


def answer_read_from_orm(answer: Answer) -> AnswerRead:
    """Map an ORM answer row to a read model.

    Args:
        answer: SQLAlchemy Answer instance.

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


def interview_read_from_orm(interview: Interview) -> InterviewRead:
    """Map an ORM interview row to a read model.

    Args:
        interview: SQLAlchemy Interview with answers loaded.

    Returns:
        Immutable InterviewRead for services and API.
    """
    return InterviewRead(
        id=interview.id,
        status=interview.status or "active",
        locale=interview.locale or "en",
        selection_spec=interview.selection_spec,
        question_ids=interview.question_ids or "[]",
        question_count=interview.question_count or 0,
        question_time_limit_seconds=interview.question_time_limit_seconds,
        answers=[answer_read_from_orm(a) for a in interview.answers],
        score=interview.score,
        overall_feedback=_parse_overall_feedback(interview.overall_feedback),
        started_at=interview.started_at,
        completed_at=interview.completed_at,
    )
