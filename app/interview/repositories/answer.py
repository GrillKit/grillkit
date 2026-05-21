# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Answer repository.

Provides data access for ``Answer`` records, including queries for
finding answers by session/question/round and creating follow-up entries.
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.shared.domain.exceptions import AnswerNotFoundError
from app.shared.infrastructure.models import Answer
from app.shared.repositories.base import SqlAlchemyRepository


class AnswerRepository(SqlAlchemyRepository[Answer]):
    """Repository for ``Answer`` entities.

    Attributes:
        _session: Active SQLAlchemy Session (inherited).
    """

    _model = Answer

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        super().__init__(session)

    # ------------------------------------------------------------------
    # Domain-specific queries
    # ------------------------------------------------------------------

    def get_by_interview_question_round(
        self, interview_id: str, question_id: str, round_num: int
    ) -> Answer:
        """Find a specific Answer by session, question, and round.

        Args:
            interview_id: The parent session UUID.
            question_id: The YAML question ID.
            round_num: The answer round (0 = initial, 1+ = follow-ups).

        Returns:
            The matching Answer.

        Raises:
            AnswerNotFoundError: If the record is not found.
        """
        answer = (
            self._session.query(Answer)
            .filter_by(
                interview_id=interview_id,
                question_id=question_id,
                round=round_num,
            )
            .first()
        )
        if not answer:
            raise AnswerNotFoundError(interview_id, question_id, round_num)
        return answer

    def get_max_round(self, interview_id: str, question_id: str) -> int:
        """Get the highest round number for a given session+question.

        Args:
            interview_id: The parent session UUID.
            question_id: The YAML question ID.

        Returns:
            The maximum round number (0 if none exist).
        """
        result = (
            self._session.query(Answer.round)
            .filter_by(
                interview_id=interview_id,
                question_id=question_id,
            )
            .order_by(Answer.round.desc())
            .first()
        )
        return result[0] if result else 0

    def list_answered(self, interview_id: str) -> Sequence[Answer]:
        """Return all answered records for a session.

        Args:
            interview_id: The session UUID.

        Returns:
            Sequence of Answer records with non-null answer_text.
        """
        return (
            self._session.query(Answer)
            .filter_by(interview_id=interview_id)
            .filter(Answer.answer_text.isnot(None))
            .order_by(Answer.order, Answer.round)
            .all()
        )

    def list_by_interview(self, interview_id: str) -> Sequence[Answer]:
        """Return all Answer records for a session, ordered.

        Args:
            interview_id: The session UUID.

        Returns:
            Sequence of Answer records ordered by (order, round).
        """
        return (
            self._session.query(Answer)
            .filter_by(interview_id=interview_id)
            .order_by(Answer.order, Answer.round)
            .all()
        )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def set_answer_text(self, answer: Answer, text: str) -> None:
        """Set the user's answer text on a record.

        Args:
            answer: The Answer entity (must be attached to this repo's session).
            text: The user's answer text.
        """
        answer.answer_text = text

    def set_evaluation(self, answer: Answer, score: int, feedback: str) -> None:
        """Set AI evaluation results on a record.

        Args:
            answer: The Answer entity.
            score: AI score (1-5).
            feedback: AI feedback text.
        """
        answer.score = score
        answer.feedback = feedback
