# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session completion service.

This module provides service for completing interview sessions and generating
final AI evaluations.
"""

import logging

from app.ai.base import AIProvider
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.mappers import interview_to_read
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.evaluator.service import InterviewEvaluatorService
from app.interview.services.events import (
    EvaluatingEvent,
    InterviewCompletedEvent,
    InterviewEvent,
)
from app.interview.services.rules.selection import selection_sources_summary

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
        with InterviewUnitOfWork() as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)

            questions_answers = [
                {
                    "question_id": answer.question_id,
                    "question_text": answer.question_text,
                    "answer_text": answer.answer_text,
                    "score": answer.score,
                    "round": answer.round,
                }
                for answer in aggregate.answers
                if answer.answer_text is not None
            ]
            normalized_breakdown = aggregate.per_question_score_breakdown()
            locale = aggregate.locale
            sources_text = selection_sources_summary(aggregate.selection)

        events: list[InterviewEvent] = [EvaluatingEvent()]

        interview_eval = await InterviewEvaluatorService.evaluate_interview(
            provider=provider,
            questions_answers=questions_answers,
            sources_text=sources_text,
            locale=locale,
        )

        interview_eval = interview_eval.model_copy(
            update={"score_breakdown": normalized_breakdown}
        )

        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            completed = aggregate.with_session_completed(interview_eval.model_dump())
            score = completed.score or 0
            uow.interviews.save_aggregate(completed)
            interview_read = interview_to_read(completed)

        max_score = DashboardBuilder.compute_max_score(
            interview_read, interview_eval.score_breakdown or None
        )
        events.append(
            InterviewCompletedEvent(
                overall_feedback=interview_eval.model_dump(),
                score=score,
                max_score=max_score,
            )
        )
        return events
