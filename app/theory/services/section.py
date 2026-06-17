# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section orchestration service."""

from __future__ import annotations

from typing import ClassVar, Literal

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.section_service_support import SectionFeedbackPrefetch
from app.interview.services.sections import (
    SectionEvaluationSummary,
    SectionPageContext,
)
from app.theory.services.evaluator.service import TheoryEvaluatorService
from app.theory.services.query import TheoryQueryService


async def _evaluate_theory_section_feedback(
    provider: object,
    summary: SectionEvaluationSummary,
    sources_text: str,
    locale: str,
) -> tuple[dict[str, object], int] | None:
    """Run the theory section LLM evaluation for prefetch.

    Args:
        provider: Configured AI provider instance.
        summary: Section evaluation summary with per-task rows.
        sources_text: Human-readable selection summary.
        locale: Section locale for prompts.

    Returns:
        Feedback payload and section score.
    """
    section_eval = await TheoryEvaluatorService.evaluate_section(
        provider=provider,  # type: ignore[arg-type]
        questions_answers=list(summary.items),
        sources_text=sources_text,
        locale=locale,
    )
    return section_eval.model_dump(), summary.score


def _build_theory_feedback_prefetch(
    uow: InterviewUnitOfWork,
    query: TheoryQueryService | None = None,
) -> SectionFeedbackPrefetch:
    """Build theory section feedback prefetch helpers for a unit of work.

    Args:
        uow: Active application unit of work.
        query: Optional query helper sharing the same unit of work.

    Returns:
        Configured prefetch helper for theory sections.
    """
    resolved_query = query or TheoryQueryService(uow)
    return SectionFeedbackPrefetch(
        uow,
        section_name="theory",
        build=lambda scoped_uow: _build_theory_feedback_prefetch(scoped_uow),
        query=resolved_query,
        get_section=lambda scoped_uow, interview_id: (
            scoped_uow.theory_sections.get_aggregate(interview_id)
        ),
        save_section=lambda scoped_uow, section: (
            scoped_uow.theory_sections.save_aggregate(section)
        ),
        evaluate_section=_evaluate_theory_section_feedback,
    )


class TheorySectionService:
    """Theory section lifecycle hooks and read helpers."""

    section_kind: ClassVar[Literal["theory"]] = "theory"

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        query: TheoryQueryService | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this section scope.
            query: Optional theory query helper sharing the same unit of work.
        """
        self._uow = uow
        self._query = query or TheoryQueryService(uow)
        self._feedback = _build_theory_feedback_prefetch(uow, self._query)

    def is_complete(self, interview_id: str) -> bool:
        """Return whether all theory tasks in the section are answered.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when every task has answer text.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            return False
        return section.is_complete()

    def is_user_facing(self, interview_id: str) -> bool:
        """Return whether the user should interact with the theory section now.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when unanswered theory tasks remain.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            return False
        return not section.is_complete()

    def activate_if_pending(self, interview_id: str) -> bool:
        """Theory sections are created active; nothing to promote.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Always False.
        """
        del interview_id
        return False

    def get_page_context(self, interview_id: str) -> SectionPageContext | None:
        """Return theory section page metadata for session composition.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section page context, or None when no theory section exists.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            return None
        return SectionPageContext(
            section="theory",
            active=not section.is_complete(),
            complete=section.is_complete(),
        )

    def get_evaluation_summary(
        self,
        interview_id: str,
    ) -> SectionEvaluationSummary | None:
        """Return theory evaluation summary for session completion.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section summary, or None when no theory section exists.
        """
        return self._query.get_evaluation_summary(interview_id)

    def on_phase_complete(self, interview_id: str) -> None:
        """Schedule background prefetch of theory section narrative feedback.

        Idempotent: skips when feedback is already cached.

        Args:
            interview_id: Parent interview UUID.
        """
        self._feedback.on_phase_complete(interview_id)

    async def ensure_section_feedback(self, interview_id: str) -> None:
        """Synchronously prefetch section feedback before session completion.

        Idempotent: skips when feedback is already cached or the section is
        incomplete.

        Args:
            interview_id: Parent interview UUID.
        """
        await self._feedback.ensure_section_feedback(interview_id)
