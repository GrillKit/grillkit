# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session completion service.

This module provides service for completing interview sessions and generating
final AI evaluations from merged section summaries.
"""

from dataclasses import replace
import logging

from app.ai.base import AIProvider
from app.coding.services.query import CodingQueryService
from app.coding.services.section import CodingSectionService
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.evaluation_aggregator import (
    SessionEvaluationAggregator,
    attach_session_score_breakdown,
)
from app.interview.services.events import (
    EvaluatingEvent,
    InterviewCompletedEvent,
    InterviewEvent,
)
from app.interview.services.read_model import load_interview_read
from app.interview.services.rules.selection import selection_sources_summary
from app.interview.services.session_evaluator import SessionEvaluatorService
from app.theory.services.query import TheoryQueryService
from app.theory.services.section import TheorySectionService

logger = logging.getLogger(__name__)


class SessionCompletionService:
    """Service for completing interview sessions."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    async def complete_session(
        self,
        interview_id: str,
        provider: AIProvider,
    ) -> list[InterviewEvent]:
        """Complete a session and generate final AI evaluation.

        Orchestrates:
        1. Load per-section evaluation summaries
        2. Merge summaries for session-level evaluation
        3. Save overall_feedback and mark session completed

        Args:
            interview_id: The session UUID.
            provider: AI provider for final evaluation.

        Returns:
            Semantic events for optional WebSocket delivery.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
        """
        aggregate = self._uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            raise InterviewNotFoundError(interview_id)

        try:
            locale = aggregate.locale
            session = aggregate.selection
            theory_query = TheoryQueryService(self._uow)
            coding_query = CodingQueryService(self._uow)
            theory_section = TheorySectionService(self._uow, query=theory_query)
            coding_section = CodingSectionService(self._uow, query=coding_query)

            sources_parts: list[str] = []
            if session.theory.enabled:
                theory_sources = theory_query.sources_text_for_section(interview_id)
                if theory_sources:
                    sources_parts.append(theory_sources)
            if session.coding.enabled:
                coding_sources = coding_query.sources_text_for_section(interview_id)
                if coding_sources:
                    sources_parts.append(coding_sources)
            sources_text = (
                "; ".join(sources_parts)
                if sources_parts
                else selection_sources_summary(aggregate.selection.theory_selection)
            )

            await theory_section.ensure_section_feedback(interview_id)
            await coding_section.ensure_section_feedback(interview_id)

            theory_summary = theory_query.get_evaluation_summary(interview_id)
            if (
                theory_summary is not None
                and session.theory.enabled
                and not theory_section.is_complete(interview_id)
            ):
                theory_summary = replace(theory_summary, skipped=True)

            coding_summary = coding_query.get_evaluation_summary(interview_id)
            if (
                coding_summary is not None
                and session.coding.enabled
                and not coding_section.is_complete(interview_id)
            ):
                coding_summary = replace(coding_summary, skipped=True)

            merged = SessionEvaluationAggregator.merge(theory_summary, coding_summary)

            events: list[InterviewEvent] = [EvaluatingEvent()]

            session_eval = await SessionEvaluatorService.evaluate_session(
                merged,
                provider=provider,
                locale=locale,
                sources_text=sources_text,
            )
            interview_eval = attach_session_score_breakdown(session_eval, merged)

            aggregate = self._uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            completed = aggregate.with_session_completed(interview_eval.model_dump())
            self._uow.interviews.save_aggregate(completed)
            interview_read = load_interview_read(self._uow, interview_id)
            if interview_read is None:
                raise InterviewNotFoundError(interview_id)
            score = SessionEvaluationAggregator.total_score_from_breakdown(
                interview_eval.score_breakdown
            )

            max_score = DashboardBuilder.compute_max_score(
                interview_read,
                interview_eval.score_breakdown or None,
                uow=self._uow,
            )
            events.append(
                InterviewCompletedEvent(
                    overall_feedback=interview_eval.model_dump(),
                    score=score,
                    max_score=max_score,
                )
            )
            self._uow.commit()
            return events
        except Exception:
            self._uow.rollback()
            raise
