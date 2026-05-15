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
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, selectinload

from ..database import get_session, session_scope
from ..models import Answer, InterviewSession
from ..questions import list_categories, load_category
from .config import ConfigService
from .interview_evaluator import InterviewEvaluatorService

logger = logging.getLogger(__name__)

# Type alias for WebSocket event send callbacks
WsSend = Callable[[dict[str, Any]], None]


# ---------------------------------------------------------------------------
# Module-level DB helpers (reduce boilerplate across service methods)
# ---------------------------------------------------------------------------


def _get_answer_record(
    db: Session, session_id: str, question_id: str, round_num: int
) -> Answer:
    """Look up an Answer record by session, question, and round.

    Args:
        db: Active DB session.
        session_id: The session UUID.
        question_id: The question ID.
        round_num: The answer round number.

    Returns:
        The matching Answer record.

    Raises:
        ValueError: If not found.
    """
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
    return answer


def _add_follow_up_record(
    db: Session, session_id: str, question_id: str, follow_up_text: str
) -> Answer:
    """Create a follow-up Answer record in an existing DB session.

    Args:
        db: Active DB session.
        session_id: The session UUID.
        question_id: The question ID.
        follow_up_text: The follow-up question text.

    Returns:
        The newly created Answer record.

    Raises:
        ValueError: If original question not found.
    """
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

    # Get the original answer to copy metadata
    original = _get_answer_record(db, session_id, question_id, 0)

    follow_up = Answer(
        interview_session_id=session_id,
        question_id=question_id,
        order=original.order,
        round=next_round,
        question_text=follow_up_text,
        question_code=original.question_code,
    )
    db.add(follow_up)
    db.flush()
    db.refresh(follow_up)
    return follow_up


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

        with session_scope() as db:
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

            db.refresh(interview_session)
            return interview_session

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
        db: Session | None = None,
    ) -> Answer:
        """Record a user's answer for a question.

        Args:
            session_id: The session UUID.
            question_id: The question ID from the YAML bank.
            answer_text: The user's answer text.
            round_num: Follow-up round number (0 = initial, 1+ = follow-ups).
            db: Optional existing DB session. If provided, caller manages commit.

        Returns:
            The updated Answer record.

        Raises:
            ValueError: If session or question not found.
        """
        if db is not None:
            answer = _get_answer_record(db, session_id, question_id, round_num)
            answer.answer_text = answer_text
            db.flush()
            db.refresh(answer)
            return answer

        with session_scope() as sess:
            answer = _get_answer_record(sess, session_id, question_id, round_num)
            answer.answer_text = answer_text
            sess.refresh(answer)
            return answer

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

        Raises:
            ValueError: If original question not found.
        """
        with session_scope() as db:
            return _add_follow_up_record(db, session_id, question_id, follow_up_text)

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
        with session_scope() as db:
            session = db.query(InterviewSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            scores = [a.score for a in session.answers if a.score is not None]
            session.score = sum(scores) if scores else 0
            session.status = "completed"
            session.completed_at = datetime.now(UTC)
            db.refresh(session)
            return session

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
        with session_scope() as db:
            answer = _get_answer_record(db, session_id, question_id, round_num)
            answer.score = score
            answer.feedback = feedback
            db.refresh(answer)
            return answer

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
        with session_scope() as db:
            session = db.query(InterviewSession).filter_by(id=session_id).first()
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            session.overall_feedback = evaluation_json
            db.refresh(session)
            return session

    # ------------------------------------------------------------------
    # Orchestration methods (called by API endpoints)
    # ------------------------------------------------------------------

    @staticmethod
    def _find_current_answer(session: InterviewSession, question_id: str) -> Answer:
        """Find the current unanswered answer for a question (any round).

        Args:
            session: The interview session with eager-loaded answers.
            question_id: The question ID to look for.

        Returns:
            The first unanswered Answer record.

        Raises:
            ValueError: If no unanswered answer is found.
        """
        for ans in session.answers:
            if ans.question_id == question_id and ans.answer_text is None:
                return ans
        raise ValueError(
            f"Unanswered answer not found: session={session.id}, question={question_id}"
        )

    @staticmethod
    def _find_next_unanswered(
        session: InterviewSession, current_index: int
    ) -> Answer | None:
        """Find the next unanswered question in the session.

        Scans forward from *current_index* for the first Answer with
        ``answer_text IS NULL``.  Answers are sorted by ``(order, round)``,
        so this naturally handles follow-ups too.

        Args:
            session: The interview session with eager-loaded answers.
            current_index: Index of the current answer in ``session.answers``.

        Returns:
            The next unanswered Answer, or None if all questions are answered.
        """
        for ans in session.answers[current_index + 1 :]:
            if ans.answer_text is None:
                return ans
        return None

    @staticmethod
    async def _run_ai_evaluation(
        answer: Answer,
        answer_text: str,
        session: InterviewSession,
        provider: Any,
    ) -> tuple[Any, bool, str | None]:
        """Run AI evaluation and decide follow-up.

        Delegates to ``evaluate_answer`` (round 0) or ``evaluate_follow_up``
        (round >= 1).

        Args:
            answer: The Answer record being evaluated.
            answer_text: The user's answer text.
            session: The interview session (for follow-up context).
            provider: Configured AI provider.

        Returns:
            Tuple of (evaluation, follow_up_needed, follow_up_text).
        """
        question_id = answer.question_id
        answer_round = answer.round

        if answer_round == 0:
            evaluation = await InterviewEvaluatorService.evaluate_answer(
                provider=provider,
                question_text=answer.question_text,
                answer_text=answer_text,
                question_code=answer.question_code,
            )
            follow_up_needed = evaluation.follow_up_needed and bool(
                evaluation.follow_up_question
            )
            follow_up_text = evaluation.follow_up_question
        else:
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
                question_text=initial_answer.question_text
                if initial_answer
                else answer.question_text,
                initial_answer=initial_answer.answer_text if initial_answer else "",
                follow_up_question=answer.question_text,
                follow_up_answer=answer_text,
                question_code=answer.question_code,
            )
            follow_up_needed = (
                evaluation.needs_further_follow_up
                and bool(evaluation.follow_up_question)
                and answer_round < InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH
            )
            follow_up_text = evaluation.follow_up_question

        return evaluation, follow_up_needed, follow_up_text

    @staticmethod
    def _build_feedback_ws_event(
        evaluation: Any,
        answer: Answer,
        follow_up_needed: bool,
        follow_up_text: str | None,
        next_question: Answer | None,
    ) -> dict[str, Any]:
        """Build the feedback WebSocket event dict.

        Args:
            evaluation: The AI evaluation result.
            answer: The evaluated Answer record.
            follow_up_needed: Whether a follow-up was generated.
            follow_up_text: The follow-up question text, if any.
            next_question: The next unanswered question, if any.

        Returns:
            WebSocket event dict.
        """
        ws_event: dict[str, Any] = {
            "type": "feedback",
            "question_id": answer.question_id,
            "order": answer.order,
            "round": answer.round,
            "score": evaluation.score,
            "feedback": evaluation.feedback,
            "follow_up_question": follow_up_text if follow_up_needed else None,
            "next_question": (
                {
                    "question_id": next_question.question_id,
                    "order": next_question.order,
                    "question_text": next_question.question_text,
                    "question_code": next_question.question_code,
                }
                if next_question
                else None
            ),
        }

        # Strengths/weaknesses are only returned for initial (round=0) evaluations
        if answer.round == 0:
            ws_event["strengths"] = getattr(evaluation, "strengths", None)
            ws_event["weaknesses"] = getattr(evaluation, "weaknesses", None)

        return ws_event

    @staticmethod
    async def _evaluate_and_save(
        session: InterviewSession,
        current_answer: Answer,
        answer_text: str,
        current_index: int,
        ws_send: WsSend | None = None,
    ) -> None:
        """Evaluate an answer with AI, save results, and optionally generate follow-ups.

        Args:
            session: The interview session.
            current_answer: The Answer record being evaluated.
            answer_text: The user's answer text.
            current_index: Index of *current_answer* in ``session.answers``.
            ws_send: Optional callback for WebSocket events.
        """
        if ws_send:
            ws_send({"type": "evaluating"})

        provider = None
        try:
            provider = ConfigService.create_provider_from_config()

            (
                evaluation,
                follow_up_needed,
                follow_up_text,
            ) = await InterviewSessionService._run_ai_evaluation(
                answer=current_answer,
                answer_text=answer_text,
                session=session,
                provider=provider,
            )
        finally:
            if provider is not None:
                await provider.close()

        # Save evaluation results to DB
        with session_scope() as db:
            answer = _get_answer_record(
                db,
                session_id=session.id,
                question_id=current_answer.question_id,
                round_num=current_answer.round,
            )
            answer.score = evaluation.score
            answer.feedback = evaluation.feedback

            # Handle follow-up creation within the same session
            next_question: Answer | None = None
            if follow_up_needed:
                follow_up = _add_follow_up_record(
                    db,
                    session_id=session.id,
                    question_id=current_answer.question_id,
                    follow_up_text=follow_up_text,
                )
                session.answers.append(follow_up)
            else:
                # Only look ahead when there's no follow-up
                next_question = InterviewSessionService._find_next_unanswered(
                    session, current_index
                )

        # Build and send WS event (outside DB session)
        if ws_send:
            ws_event = InterviewSessionService._build_feedback_ws_event(
                evaluation=evaluation,
                answer=current_answer,
                follow_up_needed=follow_up_needed,
                follow_up_text=follow_up_text,
                next_question=next_question,
            )
            ws_send(ws_event)

    @staticmethod
    async def process_answer_submission(
        session_id: str,
        question_id: str,
        answer_text: str,
        ws_send: WsSend | None = None,
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
            ws_send: Optional callback for WebSocket events.

        Raises:
            ValueError: If provider not configured or session not found.
        """
        session = InterviewSessionService.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        current_answer = InterviewSessionService._find_current_answer(
            session, question_id
        )
        current_index = session.answers.index(current_answer)

        # Save the answer text to DB
        with session_scope() as db:
            answer = _get_answer_record(
                db,
                session_id=session_id,
                question_id=question_id,
                round_num=current_answer.round,
            )
            answer.answer_text = answer_text

        if ws_send:
            ws_send({"type": "saved"})

        # Evaluate with AI (opens its own DB session for saving results)
        await InterviewSessionService._evaluate_and_save(
            session=session,
            current_answer=current_answer,
            answer_text=answer_text,
            current_index=current_index,
            ws_send=ws_send,
        )

    @staticmethod
    async def process_session_completion(
        session_id: str,
        ws_send: WsSend | None = None,
    ) -> None:
        """Complete a session and generate final AI evaluation.

        Orchestrates:
        1. Build Q&A summary from all answers
        2. Evaluate with AI
        3. Save overall_feedback
        4. Mark session as completed

        Args:
            session_id: The session UUID.
            ws_send: Optional callback for WebSocket events.

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

        if ws_send:
            ws_send({"type": "evaluating"})

        # Get AI provider
        provider = None
        try:
            provider = ConfigService.create_provider_from_config()
            session_eval = await InterviewEvaluatorService.evaluate_session(
                provider=provider,
                questions_answers=questions_answers,
                level=session.level,
                category=session.category,
            )
        finally:
            if provider is not None:
                await provider.close()

        # Wrap leftover DB writes in a single transaction
        with session_scope() as db:
            # Load session in this transaction context
            db_session = db.query(InterviewSession).filter_by(id=session_id).first()
            if not db_session:
                raise ValueError(f"Session not found: {session_id}")

            db_session.overall_feedback = session_eval.model_dump_json()

            scores = [a.score for a in db_session.answers if a.score is not None]
            db_session.score = sum(scores) if scores else 0
            db_session.status = "completed"
            db_session.completed_at = datetime.now(UTC)
            db.refresh(db_session)

            # Calculate max_score from score_breakdown to match the table
            max_score_total = 0
            if session_eval.score_breakdown:
                for qid, breakdown in session_eval.score_breakdown.items():
                    if qid != "total" and isinstance(breakdown, dict):
                        max_score_total += breakdown.get("max", 5)

        if ws_send:
            ws_send(
                {
                    "type": "session_completed",
                    "overall_feedback": session_eval.model_dump(),
                    "score": db_session.score,
                    "max_score": max_score_total,
                }
            )
