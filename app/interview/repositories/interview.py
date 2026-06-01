# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview repository.

Provides data access for ``Interview`` records, including
eager-loading of related answers and lookups by ID.
"""

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.mappers import (
    interview_from_orm,
    interview_to_orm_fields,
)
from app.shared.infrastructure.models import Interview
from app.shared.repositories.base import SqlAlchemyRepository


class InterviewRepository(SqlAlchemyRepository[Interview]):
    """Repository for ``Interview`` entities.

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
        """Retrieve a session by ID with eagerly loaded answers.

        Args:
            entity_id: The session UUID.

        Returns:
            Interview with answers loaded, or None.
        """
        return (
            self._session.query(Interview)
            .options(selectinload(Interview.answers))
            .filter_by(id=entity_id)
            .first()
        )

    def get_aggregate(self, entity_id: str) -> DomainInterview | None:
        """Load a domain interview aggregate with answers.

        Args:
            entity_id: The session UUID.

        Returns:
            Domain aggregate, or None when the session does not exist.
        """
        orm_interview = self.get(entity_id)
        if orm_interview is None:
            return None
        return interview_from_orm(orm_interview)

    def save_aggregate(self, interview: DomainInterview) -> None:
        """Persist mutable fields from a domain aggregate onto ORM rows.

        Updates interview scalars and answer fields that may change during
        navigation and answer submission (``answer_text``, ``score``,
        ``feedback``, ``started_at``).

        Args:
            interview: Domain aggregate previously loaded from this repository.

        Raises:
            InterviewNotFoundError: If the session row no longer exists.
        """
        orm_interview = self.get(interview.id)
        if orm_interview is None:
            raise InterviewNotFoundError(interview.id)

        for field, value in interview_to_orm_fields(interview).items():
            setattr(orm_interview, field, value)

        orm_answers_by_id = {answer.id: answer for answer in orm_interview.answers}
        for domain_answer in interview.answers:
            orm_answer = orm_answers_by_id.get(domain_answer.id)
            if orm_answer is None:
                continue
            orm_answer.answer_text = domain_answer.answer_text
            orm_answer.score = domain_answer.score
            orm_answer.feedback = domain_answer.feedback
            orm_answer.started_at = domain_answer.started_at

    def mark_completed(self, interview: Interview, score: int) -> None:
        """Persist completed session state.

        Args:
            session: The session entity (must be attached to this repo's session).
            score: Final total score for the session.
        """
        interview.score = score
        interview.status = "completed"
        interview.completed_at = datetime.now(UTC)

    def list_recent(self, limit: int = 20) -> list[Interview]:
        """Return recent interviews (active and completed), newest first.

        Sort key is ``completed_at`` when set, otherwise ``started_at``.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            Interviews with answers eagerly loaded.
        """
        sort_key = func.coalesce(Interview.completed_at, Interview.started_at)
        return (
            self._session.query(Interview)
            .options(selectinload(Interview.answers))
            .order_by(sort_key.desc())
            .limit(limit)
            .all()
        )

    def save_evaluation_feedback(
        self, interview: Interview, evaluation_json: str
    ) -> None:
        """Persist the overall_feedback JSON on a session.

        Args:
            session: The session entity.
            evaluation_json: JSON string with evaluation data.
        """
        interview.overall_feedback = evaluation_json
