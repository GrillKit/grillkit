# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session service.

This module provides the service layer for managing interview sessions,
including creation, question selection, answer submission, and completion.
"""

import json
import random
from uuid import uuid4

from sqlalchemy.orm import selectinload

from ..database import get_session
from ..models import Answer, InterviewSession
from ..questions import load_category, list_categories


class InterviewSessionService:
    """Service for managing interview sessions."""

    @staticmethod
    def get_available_categories(language: str) -> list[str]:
        """List available categories for a language across all levels.

        Args:
            language: Programming language (e.g., "python", "javascript").

        Returns:
            List of category names available for any level.
        """
        categories: set[str] = set()
        for level in ("junior", "middle", "senior"):
            categories.update(list_categories(language, level))
        return sorted(categories)

    @staticmethod
    def create_session(
        level: str,
        category: str,
        language: str = "python",
        question_count: int = 5,
    ) -> InterviewSession:
        """Create a new interview session with selected questions.

        Loads questions from YAML bank, shuffles and picks the requested
        number, then persists the session to the database.

        Args:
            level: Difficulty level (junior, middle, senior).
            category: Question category name.
            language: Programming language (default: "python").
            question_count: Number of questions for this session (default: 5).

        Returns:
            The created InterviewSession instance with answers pre-populated.

        Raises:
            ValueError: If no questions found for the given criteria.
        """
        questions = load_category(language, level, category)
        if not questions:
            raise ValueError(
                f"No questions found for {language}/{level}/{category}"
            )

        random.shuffle(questions)
        selected = questions[:question_count]
        question_ids = [q.id for q in selected]

        interview_session_id = str(uuid4())

        db = get_session()
        try:
            interview_session = InterviewSession(
                id=interview_session_id,
                level=level,
                category=category,
                question_count=len(selected),
                question_ids=json.dumps(question_ids),
                status="active",
            )
            db.add(interview_session)

            for order, q in enumerate(selected, start=1):
                answer = Answer(
                    interview_session_id=interview_session_id,
                    question_id=q.id,
                    order=order,
                    round=0,
                    question_text=q.text,
                    question_code=q.code,
                )
                db.add(answer)

            db.commit()
            db.refresh(interview_session)
            return interview_session
        finally:
            db.close()

    @staticmethod
    def get_session(session_id: str) -> InterviewSession | None:
        """Retrieve an interview session by ID.

        Args:
            session_id: The session UUID.

        Returns:
            InterviewSession with answers loaded, or None if not found.
        """
        db = get_session()
        try:
            return (
                db.query(InterviewSession)
                .options(selectinload(InterviewSession.answers))
                .filter_by(id=session_id)
                .first()
            )
        finally:
            db.close()

    @staticmethod
    def submit_answer(
        session_id: str,
        question_id: str,
        answer_text: str,
        round_num: int = 0,
    ) -> Answer:
        """Record a user's answer for a question.

        Args:
            session_id: The session UUID.
            question_id: The question ID from the YAML bank.
            answer_text: The user's answer text.
            round_num: Follow-up round number (0 = initial, 1+ = follow-ups).

        Returns:
            The updated Answer record.

        Raises:
            ValueError: If session or question not found.
        """
        db = get_session()
        try:
            answer = (
                db.query(Answer)
                .filter_by(
                    interview_session_id=session_id,
                    question_id=question_id,
                    round=round_num,
                )
                .first()
            )
            if not answer:
                raise ValueError(
                    f"Answer record not found for session={session_id}, "
                    f"question={question_id}, round={round_num}"
                )
            answer.answer_text = answer_text
            db.commit()
            db.refresh(answer)
            return answer
        finally:
            db.close()

    @staticmethod
    def add_follow_up(
        session_id: str,
        question_id: str,
        follow_up_text: str,
    ) -> Answer:
        """Add a follow-up question round for deeper probing.

        When the AI decides the user's answer is insufficient, it can
        create a follow-up round (round > 0) to dig deeper.

        Args:
            session_id: The session UUID.
            question_id: The question ID to follow up on.
            follow_up_text: The follow-up question text.

        Returns:
            The newly created Answer record for the follow-up round.
        """
        db = get_session()
        try:
            # Find the current max round for this question
            max_round = (
                db.query(Answer.round)
                .filter_by(
                    interview_session_id=session_id,
                    question_id=question_id,
                )
                .order_by(Answer.round.desc())
                .first()
            )
            next_round = (max_round[0] if max_round else 0) + 1

            # Get the original answer to copy question_text
            original = (
                db.query(Answer)
                .filter_by(
                    interview_session_id=session_id,
                    question_id=question_id,
                    round=0,
                )
                .first()
            )
            if not original:
                raise ValueError(
                    f"Original question not found: {question_id}"
                )

            follow_up = Answer(
                interview_session_id=session_id,
                question_id=question_id,
                order=original.order,
                round=next_round,
                question_text=follow_up_text,
                question_code=original.question_code,
            )
            db.add(follow_up)
            db.commit()
            db.refresh(follow_up)
            return follow_up
        finally:
            db.close()

    @staticmethod
    def complete_session(session_id: str) -> InterviewSession:
        """Mark a session as completed and calculate total score.

        Args:
            session_id: The session UUID.

        Returns:
            The updated InterviewSession with score and completed_at set.

        Raises:
            ValueError: If session not found.
        """
        db = get_session()
        try:
            session = (
                db.query(InterviewSession).filter_by(id=session_id).first()
            )
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Calculate total score from all round=0 answers
            scores = [
                a.score
                for a in session.answers
                if a.round == 0 and a.score is not None
            ]
            session.score = sum(scores) if scores else 0
            session.status = "completed"
            from datetime import datetime, timezone

            session.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()