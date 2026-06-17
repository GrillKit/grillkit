# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview repository.

Provides data access for interview session shell rows.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.mappers import (
    interview_from_orm,
    interview_shell_to_orm,
    interview_to_orm_fields,
)
from app.shared.infrastructure.models import Interview, TheorySection
from app.shared.repositories.base import SqlAlchemyRepository


class InterviewRepository(SqlAlchemyRepository[Interview]):
    """Repository for ``Interview`` shell entities.

    Attributes:
        _session: Active SQLAlchemy Session (inherited).
    """

    _model = Interview

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        super().__init__(session)

    def get(self, entity_id: str) -> Interview | None:
        """Retrieve a session shell by ID with theory section loaded.

        Args:
            entity_id: The session UUID.

        Returns:
            Interview with theory section and tasks loaded, or None.
        """
        return (
            self._session.query(Interview)
            .options(
                selectinload(Interview.theory_section).selectinload(
                    TheorySection.tasks
                ),
            )
            .filter_by(id=entity_id)
            .first()
        )

    def get_aggregate(self, entity_id: str) -> DomainInterview | None:
        """Load a domain interview shell aggregate.

        Args:
            entity_id: The session UUID.

        Returns:
            Domain shell aggregate, or None when the session does not exist.
        """
        orm_interview = self.get(entity_id)
        if orm_interview is None:
            return None
        return interview_from_orm(orm_interview)

    def list_recent_aggregates(self, limit: int = 20) -> list[DomainInterview]:
        """Return recent interview shell aggregates, newest first.

        Sort key is ``completed_at`` when set, otherwise ``started_at``.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            Domain shell aggregates in dashboard display order.
        """
        sort_key = func.coalesce(Interview.completed_at, Interview.started_at)
        rows = (
            self._session.query(Interview).order_by(sort_key.desc()).limit(limit).all()
        )
        return [interview_from_orm(row) for row in rows]

    def create_shell(self, interview: DomainInterview) -> DomainInterview:
        """Insert a new interview shell row.

        Args:
            interview: Domain shell from ``Interview.start_shell``.

        Returns:
            Reloaded domain shell after flush.

        Raises:
            InterviewNotFoundError: If reload fails after flush.
        """
        orm_interview = interview_shell_to_orm(interview)
        self._session.add(orm_interview)
        self._session.flush()
        reloaded = self.get(interview.id)
        if reloaded is None:
            raise InterviewNotFoundError(interview.id)
        return interview_from_orm(reloaded)

    def save_aggregate(self, interview: DomainInterview) -> None:
        """Persist mutable shell fields from a domain aggregate onto the ORM row.

        Args:
            interview: Domain shell previously loaded from this repository.

        Raises:
            InterviewNotFoundError: If the session row no longer exists.
        """
        orm_interview = self.get(interview.id)
        if orm_interview is None:
            raise InterviewNotFoundError(interview.id)

        for field, value in interview_to_orm_fields(interview).items():
            setattr(orm_interview, field, value)
