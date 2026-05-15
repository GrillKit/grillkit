# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session service.

This module provides the service layer for managing interview sessions,
including creation, question selection, answer submission, AI evaluation,
follow-up generation, and session completion.
"""

import json
import logging
import random
from datetime import UTC
from uuid import uuid4

from sqlalchemy.orm import selectinload

from ..database import get_session
from ..models import Answer, InterviewSession
from ..questions import list_categories, load_category
from .config import ConfigService
from .interview_evaluator import InterviewEvaluatorService

logger = logging.getLogger(__name__)


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
            raise ValueError(f"No questions found for {language}/{level}/{category}")

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
                raise ValueError(f"Original question not found: {question_id}")

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
            session = db.query(InterviewSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Calculate total score from all answered questions
            scores = [a.score for a in session.answers if a.score is not None]
            session.score = sum(scores) if scores else 0
            session.status = "completed"
            from datetime import datetime

            session.completed_at = datetime.now(UTC)
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()

    # ------------------------------------------------------------------
    # AI evaluation helpers (called by process_answer_submission)
    # ------------------------------------------------------------------

    @staticmethod
    def save_evaluation(
        session_id: str,
        question_id: str,
        round_num: int,
        score: int,
        feedback: str,
    ) -> Answer:
        """Save AI evaluation results to an Answer record.

        Args:
            session_id: The session UUID.
            question_id: The question ID.
            round_num: The answer round number.
            score: AI-assigned score (1-5).
            feedback: AI-generated feedback text.

        Returns:
            The updated Answer record.

        Raises:
            ValueError: If answer record not found.
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
                    f"Answer not found: session={session_id}, "
                    f"question={question_id}, round={round_num}"
                )
            answer.score = score
            answer.feedback = feedback
            db.commit()
            db.refresh(answer)
            return answer
        finally:
            db.close()

    @staticmethod
    def save_session_evaluation(
        session_id: str,
        evaluation_json: str,
    ) -> InterviewSession:
        """Save the final session evaluation (overall_feedback).

        Args:
            session_id: The session UUID.
            evaluation_json: JSON string with evaluation data.

        Returns:
            The updated InterviewSession.

        Raises:
            ValueError: If session not found.
        """
        db = get_session()
        try:
            session = db.query(InterviewSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            session.overall_feedback = evaluation_json
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Orchestration methods (called by API endpoints)
    # ------------------------------------------------------------------

    @staticmethod
    async def process_answer_submission(
        session_id: str,
        question_id: str,
        answer_text: str,
    ) -> None:
        """Submit an answer and evaluate it with AI.

        Orchestrates the full answer flow:
        1. Find the current unanswered answer (any round)
        2. Save the answer text to the correct round
        3. Evaluate with AI
        4. Save score/feedback
        5. Generate follow-up if needed

        Args:
            session_id: The session UUID.
            question_id: The question ID.
            answer_text: The user's answer.

        Raises:
            ValueError: If provider not configured or session not found.
        """

        # 1. Get session and find the current unanswered answer (any round)
        session = InterviewSessionService.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        current_answer = None
        for ans in session.answers:
            if ans.question_id == question_id and ans.answer_text is None:
                current_answer = ans
                break

        if not current_answer:
            raise ValueError(
                f"Unanswered answer not found: session={session_id}, "
                f"question={question_id}"
            )

        answer_round = current_answer.round

        # 2. Save the answer text to the correct round
        InterviewSessionService.submit_answer(
            session_id=session_id,
            question_id=question_id,
            answer_text=answer_text,
            round_num=answer_round,
        )

        # 3. Get AI provider
        provider = ConfigService.create_provider_from_config()
        try:
            # 4. Evaluate with AI based on the round
            if answer_round == 0:
                evaluation = await InterviewEvaluatorService.evaluate_answer(
                    provider=provider,
                    question_text=current_answer.question_text,
                    answer_text=answer_text,
                    question_code=current_answer.question_code,
                )

                # Save evaluation
                InterviewSessionService.save_evaluation(
                    session_id=session_id,
                    question_id=question_id,
                    round_num=answer_round,
                    score=evaluation.score,
                    feedback=evaluation.feedback,
                )

                # Generate follow-up if needed
                if evaluation.follow_up_needed and evaluation.follow_up_question:
                    InterviewSessionService.add_follow_up(
                        session_id=session_id,
                        question_id=question_id,
                        follow_up_text=evaluation.follow_up_question,
                    )
            else:
                # Follow-up answer (round >= 1)
                initial_answer = next(
                    (
                        a
                        for a in session.answers
                        if a.question_id == question_id and a.round == 0
                    ),
                    None,
                )

                evaluation = await InterviewEvaluatorService.evaluate_follow_up(
                    provider=provider,
                    question_text=initial_answer.question_text if initial_answer else current_answer.question_text,
                    initial_answer=initial_answer.answer_text if initial_answer else "",
                    follow_up_question=current_answer.question_text,
                    follow_up_answer=answer_text,
                    question_code=current_answer.question_code,
                )

                # Save evaluation
                InterviewSessionService.save_evaluation(
                    session_id=session_id,
                    question_id=question_id,
                    round_num=answer_round,
                    score=evaluation.score,
                    feedback=evaluation.feedback,
                )

                # Generate another follow-up if needed and under limit
                if (
                    evaluation.needs_further_follow_up
                    and evaluation.follow_up_question
                    and answer_round < InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH
                ):
                    InterviewSessionService.add_follow_up(
                        session_id=session_id,
                        question_id=question_id,
                        follow_up_text=evaluation.follow_up_question,
                    )
        finally:
            await provider.close()

    @staticmethod
    async def process_session_completion(session_id: str) -> None:
        """Complete a session and generate final AI evaluation.

        Orchestrates:
        1. Build Q&A summary from all answers
        2. Evaluate with AI
        3. Save overall_feedback
        4. Mark session as completed

        Args:
            session_id: The session UUID.

        Raises:
            ValueError: If session or provider not found.
        """
        session = InterviewSessionService.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Build questions_answers list
        questions_answers = [
            {
                "question_id": a.question_id,
                "question_text": a.question_text,
                "answer_text": a.answer_text,
                "score": a.score,
                "round": a.round,
            }
            for a in session.answers
            if a.answer_text is not None
        ]

        # Get AI provider
        provider = ConfigService.create_provider_from_config()
        try:
            # Evaluate session
            session_eval = await InterviewEvaluatorService.evaluate_session(
                provider=provider,
                questions_answers=questions_answers,
                level=session.level,
                category=session.category,
            )

            # Save overall_feedback
            InterviewSessionService.save_session_evaluation(
                session_id=session_id,
                evaluation_json=session_eval.model_dump_json(),
            )

            # Mark completed
            InterviewSessionService.complete_session(session_id)
        finally:
            await provider.close()
