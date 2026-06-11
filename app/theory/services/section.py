# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section orchestration service."""

from __future__ import annotations

from typing import ClassVar, Literal

from app.interview.services.section_service_support import (
    run_feedback_prefetch,
    schedule_feedback_prefetch,
    should_prefetch_feedback,
)
from app.interview.services.sections import (
    SectionEvaluationSummary,
    SectionPageContext,
)
from app.theory.repositories.uow import TheoryUnitOfWork
from app.theory.services.evaluator.service import TheoryEvaluatorService
from app.theory.services.query import TheoryQueryService


class TheorySectionService:
    """Theory section lifecycle hooks and read helpers."""

    section_kind: ClassVar[Literal["theory"]] = "theory"

    @staticmethod
    def is_complete(interview_id: str) -> bool:
        """Return whether all theory tasks in the section are answered.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when every task has answer text.
        """
        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                return False
            return section.is_complete()

    @staticmethod
    def is_user_facing(interview_id: str) -> bool:
        """Return whether the user should interact with the theory section now.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when unanswered theory tasks remain.
        """
        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                return False
            return not section.is_complete()

    @staticmethod
    def activate_if_pending(interview_id: str) -> bool:
        """Theory sections are created active; nothing to promote.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Always False.
        """
        del interview_id
        return False

    @staticmethod
    def get_page_context(interview_id: str) -> SectionPageContext | None:
        """Return theory section page metadata for session composition.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section page context, or None when no theory section exists.
        """
        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                return None
            return SectionPageContext(
                section="theory",
                active=not section.is_complete(),
                complete=section.is_complete(),
            )

    @staticmethod
    def get_evaluation_summary(
        interview_id: str,
    ) -> SectionEvaluationSummary | None:
        """Return theory evaluation summary for session completion.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section summary, or None when no theory section exists.
        """
        return TheoryQueryService.get_evaluation_summary(interview_id)

    @staticmethod
    def on_phase_complete(interview_id: str) -> None:
        """Schedule background prefetch of theory section narrative feedback.

        Idempotent: skips when feedback is already cached.

        Args:
            interview_id: Parent interview UUID.
        """
        if not TheorySectionService._should_prefetch_section_feedback(interview_id):
            return
        schedule_feedback_prefetch(
            lambda: TheorySectionService._prefetch_section_feedback(interview_id)
        )

    @staticmethod
    async def ensure_section_feedback(interview_id: str) -> None:
        """Synchronously prefetch section feedback before session completion.

        Idempotent: skips when feedback is already cached or the section is
        incomplete.

        Args:
            interview_id: Parent interview UUID.
        """
        await TheorySectionService._prefetch_section_feedback(interview_id)

    @staticmethod
    def _should_prefetch_section_feedback(interview_id: str) -> bool:
        """Return whether section feedback should be generated for an interview.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the theory section exists, is complete, and lacks feedback.
        """
        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            return should_prefetch_feedback(section)

    @staticmethod
    async def _prefetch_section_feedback(interview_id: str) -> None:
        """Generate and persist cached theory section feedback.

        Args:
            interview_id: Parent interview UUID.
        """
        await run_feedback_prefetch(
            interview_id,
            section_name="theory",
            should_prefetch=lambda: (
                TheorySectionService._should_prefetch_section_feedback(interview_id)
            ),
            evaluate=lambda provider: TheorySectionService._evaluate_section_feedback(
                interview_id,
                provider,
            ),
            persist=lambda payload, score: (
                TheorySectionService._persist_section_feedback(
                    interview_id,
                    payload,
                    score,
                )
            ),
        )

    @staticmethod
    async def _evaluate_section_feedback(
        interview_id: str,
        provider: object,
    ) -> tuple[dict[str, object], int] | None:
        """Run the theory section LLM evaluation.

        Args:
            interview_id: Parent interview UUID.
            provider: Configured AI provider instance.

        Returns:
            Feedback payload and section score, or None when evaluation is skipped.
        """
        summary = TheoryQueryService.get_evaluation_summary(interview_id)
        if summary is None or not summary.items:
            return None
        section_eval = await TheoryEvaluatorService.evaluate_section(
            provider=provider,  # type: ignore[arg-type]
            questions_answers=list(summary.items),
            sources_text=TheoryQueryService.sources_text_for_section(interview_id),
            locale=TheorySectionService._section_locale(interview_id),
        )
        return section_eval.model_dump(), summary.score

    @staticmethod
    def _persist_section_feedback(
        interview_id: str,
        payload: dict[str, object],
        score: int,
    ) -> None:
        """Persist prefetched theory section feedback when still absent.

        Args:
            interview_id: Parent interview UUID.
            payload: Section evaluation payload from the LLM.
            score: Earned section score.
        """
        with TheoryUnitOfWork(auto_commit=True) as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None or section.section_feedback is not None:
                return
            updated = section.with_cached_section_feedback(
                payload,
                section_score=score,
            )
            uow.theory_sections.save_aggregate(updated)

    @staticmethod
    def _section_locale(interview_id: str) -> str:
        """Load the theory section locale for evaluation prompts.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Locale code, defaulting to ``en`` when the section is missing.
        """
        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                return "en"
            return section.locale
