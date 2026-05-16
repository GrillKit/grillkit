# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session service.

This module provides the service layer for managing interview sessions,
including creation, question selection, answer submission, AI evaluation,
follow-up generation, and session completion.

The service delegates all data access to repositories and uses the
Unit of Work pattern for atomic database transactions.
"""

import json
import logging
import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..models import Answer, InterviewSession
from ..questions import list_categories, load_category
from ..uow import UnitOfWork
from .config import ConfigService
from .interview_evaluator import InterviewEvaluatorService

logger = logging.getLogger(__name__)

# Type alias for WebSocket event send callbacks
WsSend = Callable[[dict[str, Any]], None]


class InterviewSessionService:
    """Service for managing interview sessions.

    All data access is performed through repositories and the Unit of Work.
    """

    # ------------------------------------------------------------------
    # Read-only queries (no UoW needed — single reads)
    # ------------------------------------------------------------------

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
    def get_session(session_id: str) -> InterviewSession | None:
        """Retrieve an interview session by ID.

        Args:
            session_id: The session UUID.

        Returns:
            InterviewSession with answers loaded, or None if not found.
        """
        with UnitOfWork() as uow:
            return uow.sessions.get(session_id)

    # ------------------------------------------------------------------
    # Write operations (via UoW)
    # ------------------------------------------------------------------

    @staticmethod
    def create_session(
        level: str,
        category: str,
        language: str = "python",
        question_count: int = 5,
    ) -> InterviewSession:
        """Create a new interview session with selected questions.

        Loads questions from YAML bank, shuffles and picks the requested
        number, then persists the session to the database atomically.

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

        with UnitOfWork(auto_commit=True) as uow:
            session = uow.sessions.new_session(
                session_id=interview_session_id,
                level=level,
                category=category,
                question_count=len(selected),
                question_ids=question_ids,
            )
            uow.sessions.add(session)

            for order, q in enumerate(selected, start=1):
                answer = uow.answers.new_answer(
                    session_id=interview_session_id,
                    question_id=q.id,
                    order=order,
                    round_num=0,
                    question_text=q.text,
                    question_code=q.code,
                )
                uow.answers.add(answer)

            uow.flush()
            uow.session.refresh(session)
            return session

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
        with UnitOfWork(auto_commit=True) as uow:
            max_round = uow.answers.get_max_round(session_id, question_id)
            next_round = max_round + 1

            original = uow.answers.get_by_session_question_round_raise(
                session_id, question_id, 0
            )

            follow_up = uow.answers.new_follow_up(original, follow_up_text, next_round)
            uow.answers.add(follow_up)
            uow.flush()
            uow.session.refresh(follow_up)
            return follow_up

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
        with UnitOfWork(auto_commit=True) as uow:
            session = uow.sessions.get(session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            uow.sessions.complete_session(session)
            uow.session.refresh(session)
            return session

    # ------------------------------------------------------------------
    # Orchestration internals — operate on loaded models, no DB mutations
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

        evaluation: Any = None
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
                initial_answer=(initial_answer.answer_text or "") if initial_answer else "",
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

        The DB writes (score, feedback, optional follow-up) are wrapped
        in a single UnitOfWork for atomicity. The session and answer objects
        are re-loaded inside the UoW to ensure they are attached to the
        active DB session.

        Args:
            session: The interview session (may be detached — used read-only).
            current_answer: The Answer record being evaluated (may be detached).
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

        # Save evaluation results + optional follow-up atomically
        # All objects are re-loaded inside the UoW to ensure they are
        # attached to the active DB session.
        next_question: Answer | None = None
        with UnitOfWork(auto_commit=True) as uow:
            db_session = uow.sessions.get(session.id)
            if not db_session:
                raise ValueError(f"Session not found: {session.id}")

            db_answer = uow.answers.get_by_session_question_round_raise(
                session_id=session.id,
                question_id=current_answer.question_id,
                round_num=current_answer.round,
            )
            uow.answers.set_evaluation(
                db_answer, evaluation.score, evaluation.feedback
            )

            if follow_up_needed:
                max_round = uow.answers.get_max_round(
                    session.id, current_answer.question_id
                )
                next_round = max_round + 1

                original = uow.answers.get_by_session_question_round_raise(
                    session.id, current_answer.question_id, 0
                )
                follow_up = uow.answers.new_follow_up(
                    original, follow_up_text or "", next_round
                )
                uow.answers.add(follow_up)
            else:
                # Only look ahead when there's no follow-up
                next_question = InterviewSessionService._find_next_unanswered(
                    db_session, current_index
                )

        # Build and send WS event (outside UoW)
        if ws_send:
            ws_event = InterviewSessionService._build_feedback_ws_event(
                evaluation=evaluation,
                answer=current_answer,
                follow_up_needed=follow_up_needed,
                follow_up_text=follow_up_text,
                next_question=next_question,
            )
            ws_send(ws_event)

    # ------------------------------------------------------------------
    # Public orchestration methods (called by API endpoints)
    # ------------------------------------------------------------------

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

        # Save the answer text in its own transaction so it persists
        # even if the subsequent AI evaluation fails
        with UnitOfWork(auto_commit=True) as uow:
            answer = uow.answers.get_by_session_question_round_raise(
                session_id, question_id, current_answer.round
            )
            uow.answers.set_answer_text(answer, answer_text)

        if ws_send:
            ws_send({"type": "saved"})

        # Evaluate with AI (opens its own UoW for saving results)
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

        # Persist results atomically
        with UnitOfWork(auto_commit=True) as uow:
            db_session = uow.sessions.get(session_id)
            if not db_session:
                raise ValueError(f"Session not found: {session_id}")

            uow.sessions.save_evaluation_feedback(
                db_session, session_eval.model_dump_json()
            )
            uow.sessions.complete_session(db_session)
            uow.session.refresh(db_session)

            # Calculate max_score from score_breakdown
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
