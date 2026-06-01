# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session completion service.

This module provides service for completing interview sessions and generating
final AI evaluations.
"""

import logging

from app.ai.base import AIProvider
from app.interview.repositories.mappers import interview_read_to_domain
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.mappers import interview_read_from_orm
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.evaluator.service import InterviewEvaluatorService
from app.interview.services.events import (
    EvaluatingEvent,
    InterviewCompletedEvent,
    InterviewEvent,
)
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.selection import (
    get_interview_selection,
    selection_sources_summary,
)

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

        session = interview_read_to_domain(interview)
        normalized_breakdown = session.per_question_score_breakdown()
        interview_eval = interview_eval.model_copy(
            update={"score_breakdown": normalized_breakdown}
        )

        score = 0
        with InterviewUnitOfWork(auto_commit=True) as uow:
            db_interview = InterviewQuery.get_orm_or_raise(interview_id, uow=uow)

            uow.interviews.save_evaluation_feedback(
                db_interview, interview_eval.model_dump_json()
            )
            completed_read = interview_read_from_orm(db_interview)
            score = interview_read_to_domain(completed_read).total_score()
            uow.interviews.mark_completed(db_interview, score)
            interview = interview_read_from_orm(db_interview)

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
