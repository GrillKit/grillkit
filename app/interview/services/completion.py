# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session completion service.

This module provides service for completing interview sessions and generating
final AI evaluations.
"""

import logging

from app.ai.base import AIProvider
from app.interview.domain.lifecycle import (
    build_per_question_score_breakdown,
    compute_interview_score,
)
from app.interview.domain.selection import (
    get_interview_selection,
    selection_sources_summary,
)
from app.interview.domain.session import interview_view
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.evaluator.service import InterviewEvaluatorService
from app.interview.services.events import (
    EvaluatingEvent,
    InterviewCompletedEvent,
    InterviewEvent,
)
from app.interview.services.query import InterviewQuery

logger = logging.getLogger(__name__)


class InterviewCompletionService:
    """Service for completing interview sessions."""

    @staticmethod
    async def complete_interview(
        interview_id: str,
        provider: AIProvider,
    ) -> list[InterviewEvent]:
        """Complete a session and generate final AI evaluation.

        Orchestrates:
        1. Build Q&A summary from all answers
        2. Evaluate with AI
        3. Save overall_feedback
        4. Mark session as completed

        Args:
            interview_id: The session UUID.
            provider: AI provider for final evaluation.

        Returns:
            Semantic events for optional WebSocket delivery.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
        """
        interview = InterviewQuery.get_interview_or_raise(interview_id)

        questions_answers = [
            {
                "question_id": a.question_id,
                "question_text": a.question_text,
                "answer_text": a.answer_text,
                "score": a.score,
                "round": a.round,
            }
            for a in interview.answers
            if a.answer_text is not None
        ]

        events: list[InterviewEvent] = [EvaluatingEvent()]

        sources_text = selection_sources_summary(get_interview_selection(interview))
        interview_eval = await InterviewEvaluatorService.evaluate_interview(
            provider=provider,
            questions_answers=questions_answers,
            sources_text=sources_text,
            locale=interview.locale,
        )

        normalized_breakdown = build_per_question_score_breakdown(
            interview_view(interview)
        )
        interview_eval = interview_eval.model_copy(
            update={"score_breakdown": normalized_breakdown}
        )

        score = 0
        with InterviewUnitOfWork(auto_commit=True) as uow:
            db_interview = InterviewQuery.get_interview_or_raise(interview_id, uow=uow)

            uow.interviews.save_evaluation_feedback(
                db_interview, interview_eval.model_dump_json()
            )
            score = compute_interview_score(interview_view(db_interview))
            uow.interviews.mark_completed(db_interview, score)

        max_score = DashboardBuilder.compute_max_score(
            interview, interview_eval.score_breakdown or None
        )
        events.append(
            InterviewCompletedEvent(
                overall_feedback=interview_eval.model_dump(),
                score=score,
                max_score=max_score,
            )
        )
        return events
