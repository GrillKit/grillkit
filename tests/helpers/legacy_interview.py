# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Helpers for inserting interview rows before session_mode migration."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_pre_session_mode_interview(
    session: Session,
    *,
    interview_id: str,
    selection_spec: str,
    locale: str = "en",
    question_count: int = 5,
    question_time_limit_seconds: int | None = None,
) -> None:
    """Insert an interview row using the pre-0006 interviews schema.

    Args:
        session: Active SQLAlchemy session bound to a pre-0006 database.
        interview_id: Interview UUID primary key.
        selection_spec: Raw selection_spec JSON string.
        locale: Interview locale.
        question_count: Legacy question count column value.
        question_time_limit_seconds: Legacy per-round timer column value.
    """
    session.execute(
        text(
            """
            INSERT INTO interviews (
                id,
                locale,
                selection_spec,
                question_count,
                question_ids,
                question_time_limit_seconds,
                status
            ) VALUES (
                :id,
                :locale,
                :spec,
                :question_count,
                '[]',
                :timer,
                'active'
            )
            """
        ),
        {
            "id": interview_id,
            "locale": locale,
            "spec": selection_spec,
            "question_count": question_count,
            "timer": question_time_limit_seconds,
        },
    )
    session.commit()
