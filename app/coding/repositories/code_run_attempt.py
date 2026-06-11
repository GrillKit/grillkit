# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Repository for immutable coding Run attempt rows."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.coding.domain.entities import CodeRunAttempt as DomainCodeRunAttempt
from app.coding.repositories.mappers import (
    code_run_attempt_from_orm,
    domain_code_run_attempt_to_orm,
)
from app.shared.infrastructure.models import CodeRunAttempt


class CodeRunAttemptRepository:
    """Persistence access for ``code_run_attempts`` rows.

    Attributes:
        _session: Active SQLAlchemy Session.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        self._session = session

    def count_for_task(self, coding_task_id: int) -> int:
        """Return how many Run attempts exist for a coding task row.

        Args:
            coding_task_id: Parent ``coding_tasks.id``.

        Returns:
            Number of persisted attempts.
        """
        return (
            self._session.query(func.count(CodeRunAttempt.id))
            .filter(CodeRunAttempt.coding_task_id == coding_task_id)
            .scalar()
            or 0
        )

    def list_for_task(self, coding_task_id: int) -> tuple[DomainCodeRunAttempt, ...]:
        """Load attempts for a coding task ordered by attempt number.

        Args:
            coding_task_id: Parent ``coding_tasks.id``.

        Returns:
            Immutable domain attempts in ascending ``attempt_no`` order.
        """
        rows = (
            self._session.query(CodeRunAttempt)
            .filter_by(coding_task_id=coding_task_id)
            .order_by(CodeRunAttempt.attempt_no.asc())
            .all()
        )
        return tuple(code_run_attempt_from_orm(row) for row in rows)

    def create(self, attempt: DomainCodeRunAttempt) -> DomainCodeRunAttempt:
        """Insert one Run attempt row.

        Args:
            attempt: Domain attempt with ``NEW_ID``.

        Returns:
            Reloaded domain attempt including the assigned primary key.
        """
        orm_row = domain_code_run_attempt_to_orm(attempt)
        self._session.add(orm_row)
        self._session.flush()
        self._session.refresh(orm_row)
        return code_run_attempt_from_orm(orm_row)
