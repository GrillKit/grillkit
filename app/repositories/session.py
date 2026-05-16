# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""InterviewSession repository.

Provides data access for ``InterviewSession`` records, including
eager-loading of related answers and lookups by ID.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from ..models import InterviewSession
from .base import SqlAlchemyRepository


class InterviewSessionRepository(SqlAlchemyRepository[InterviewSession]):
    """Repository for ``InterviewSession`` entities.

    Attributes:
        _session: Active SQLAlchemy Session (inherited).
    """

    _model = InterviewSession

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        super().__init__(session)

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def get(self, entity_id: str) -> InterviewSession | None:
        """Retrieve a session by ID with eagerly loaded answers.

        Args:
            entity_id: The session UUID.

        Returns:
            InterviewSession with answers loaded, or None.
        """
        return (
            self._session.query(InterviewSession)
            .options(selectinload(InterviewSession.answers))
            .filter_by(id=entity_id)
            .first()
        )

    # ------------------------------------------------------------------
    # Domain-specific queries
    # ------------------------------------------------------------------

    def get_by_id_with_answers(self, session_id: str) -> InterviewSession | None:
        """Explicit alias for ``get()`` – always eager-loads answers.

        Args:
            session_id: The session UUID.

        Returns:
            InterviewSession with answers, or None.
        """
        return self.get(session_id)

    def complete_session(
        self, session: InterviewSession, overall_feedback_json: str | None = None
    ) -> None:
        """Mark a session as completed with optional evaluation data.

        Calculates the total score from all scored answers.

        Args:
            session: The session entity (must be attached to this repo's session).
            overall_feedback_json: Optional JSON evaluation string.
        """
        scores = [a.score for a in session.answers if a.score is not None]
        session.score = sum(scores) if scores else 0
        session.status = "completed"
        session.completed_at = datetime.now(UTC)
        if overall_feedback_json is not None:
            session.overall_feedback = overall_feedback_json

    def save_evaluation_feedback(
        self, session: InterviewSession, evaluation_json: str
    ) -> None:
        """Persist the overall_feedback JSON on a session.

        Args:
            session: The session entity.
            evaluation_json: JSON string with evaluation data.
        """
        session.overall_feedback = evaluation_json

    # ------------------------------------------------------------------
    # Factories (moved from old InterviewSessionService)
    # ------------------------------------------------------------------

    @staticmethod
    def new_session(
        session_id: str,
        level: str,
        category: str,
        question_count: int,
        question_ids: list[str],
    ) -> InterviewSession:
        """Create a new InterviewSession instance (not persisted).

        Args:
            session_id: UUID string.
            level: Difficulty level.
            category: Question category.
            question_count: Number of questions.
            question_ids: Ordered list of YAML question IDs.

        Returns:
            Unsaved InterviewSession instance.
        """
        return InterviewSession(
            id=session_id,
            level=level,
            category=category,
            question_count=question_count,
            question_ids=json.dumps(question_ids),
            status="active",
        )
