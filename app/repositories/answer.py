# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Answer repository.

Provides data access for ``Answer`` records, including queries for
finding answers by session/question/round and creating follow-up entries.
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..models import Answer, InterviewSession
from .base import SqlAlchemyRepository


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

    def get_by_session_question_round(
        self, session_id: str, question_id: str, round_num: int
    ) -> Answer | None:
        """Find a specific Answer by session, question, and round.

        Args:
            session_id: The parent session UUID.
            question_id: The YAML question ID.
            round_num: The answer round (0 = initial, 1+ = follow-ups).

        Returns:
            The matching Answer, or None.
        """
        return (
            self._session.query(Answer)
            .filter_by(
                interview_session_id=session_id,
                question_id=question_id,
                round=round_num,
            )
            .first()
        )

    def get_by_session_question_round_raise(
        self, session_id: str, question_id: str, round_num: int
    ) -> Answer:
        """Like ``get_by_session_question_round`` but raises on missing.

        Args:
            session_id: The parent session UUID.
            question_id: The YAML question ID.
            round_num: The answer round.

        Returns:
            The matching Answer.

        Raises:
            ValueError: If the record is not found.
        """
        answer = self.get_by_session_question_round(session_id, question_id, round_num)
        if not answer:
            raise ValueError(
                f"Answer not found: session={session_id}, "
                f"question={question_id}, round={round_num}"
            )
        return answer

    def get_max_round(self, session_id: str, question_id: str) -> int:
        """Get the highest round number for a given session+question.

        Args:
            session_id: The parent session UUID.
            question_id: The YAML question ID.

        Returns:
            The maximum round number (0 if none exist).
        """
        result = (
            self._session.query(Answer.round)
            .filter_by(
                interview_session_id=session_id,
                question_id=question_id,
            )
            .order_by(Answer.round.desc())
            .first()
        )
        return result[0] if result else 0

    def list_answered(self, session_id: str) -> Sequence[Answer]:
        """Return all answered records for a session.

        Args:
            session_id: The session UUID.

        Returns:
            Sequence of Answer records with non-null answer_text.
        """
        return (
            self._session.query(Answer)
            .filter_by(interview_session_id=session_id)
            .filter(Answer.answer_text.isnot(None))
            .order_by(Answer.order, Answer.round)
            .all()
        )

    def list_by_session(self, session_id: str) -> Sequence[Answer]:
        """Return all Answer records for a session, ordered.

        Args:
            session_id: The session UUID.

        Returns:
            Sequence of Answer records ordered by (order, round).
        """
        return (
            self._session.query(Answer)
            .filter_by(interview_session_id=session_id)
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

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @staticmethod
    def new_answer(
        session_id: str,
        question_id: str,
        order: int,
        round_num: int,
        question_text: str,
        question_code: str | None = None,
    ) -> Answer:
        """Create a new Answer instance (not persisted).

        Args:
            session_id: Parent session UUID.
            question_id: YAML question ID.
            order: Display order (1-based).
            round_num: Round number (0=initial, 1+=follow-up).
            question_text: Snapshot of the question text.
            question_code: Optional code snippet.

        Returns:
            Unsaved Answer instance.
        """
        return Answer(
            interview_session_id=session_id,
            question_id=question_id,
            order=order,
            round=round_num,
            question_text=question_text,
            question_code=question_code,
        )

    @staticmethod
    def new_follow_up(
        original: Answer, follow_up_text: str, next_round: int
    ) -> Answer:
        """Create a follow-up Answer based on an existing one.

        Args:
            original: The original Answer (round=0) to copy metadata from.
            follow_up_text: The follow-up question text.
            next_round: The round number for the new follow-up.

        Returns:
            Unsaved Answer instance for the follow-up.
        """
        return Answer(
            interview_session_id=original.interview_session_id,
            question_id=original.question_id,
            order=original.order,
            round=next_round,
            question_text=follow_up_text,
            question_code=original.question_code,
        )
