# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section orchestration service."""

from __future__ import annotations

from typing import ClassVar, Literal

from app.coding.repositories.uow import CodingUnitOfWork
from app.coding.services.evaluator.service import CodingEvaluatorService
from app.coding.services.query import CodingQueryService
from app.interview.services.section_service_support import (
    run_feedback_prefetch,
    schedule_feedback_prefetch,
    should_prefetch_feedback,
)
from app.interview.services.sections import (
    SectionEvaluationSummary,
    SectionPageContext,
    prior_sections_complete_for,
)


class CodingSectionService:
    """Coding section lifecycle hooks and read helpers."""

    section_kind: ClassVar[Literal["coding"]] = "coding"

    @staticmethod
    def is_complete(interview_id: str) -> bool:
        """Return whether all coding tasks in the section are submitted.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when every task has submitted code or the section was skipped.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return False
            if section.status in {"skipped", "completed"}:
                return True
            return section.is_complete()

    @staticmethod
    def is_user_facing(interview_id: str) -> bool:
        """Return whether the user should interact with the coding section now.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the coding section is active and still has work remaining.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return False
            complete = (
                section.status in {"skipped", "completed"} or section.is_complete()
            )
            return section.status == "active" and not complete

    @staticmethod
    def activate_if_pending(interview_id: str) -> bool:
        """Promote a pending coding section to active when prior phases finish.

        Starts the per-task timer on the first unsubmitted task when enabled.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the section was activated in this call.
        """
        return CodingSectionService.activate_pending(interview_id)

    @staticmethod
    def get_page_context(interview_id: str) -> SectionPageContext | None:
        """Return coding section page metadata for session composition.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section page context, or None when no coding section exists.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return None
            complete = (
                section.status in {"skipped", "completed"} or section.is_complete()
            )
            active = section.status == "active" and not complete
            return SectionPageContext(
                section="coding",
                active=active,
                complete=complete,
            )

    @staticmethod
    def get_evaluation_summary(
        interview_id: str,
    ) -> SectionEvaluationSummary | None:
        """Return coding evaluation summary for session completion.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section summary, or None when no coding section exists.
        """
        return CodingQueryService.get_evaluation_summary(interview_id)

    @staticmethod
    def activate_pending(interview_id: str) -> bool:
        """Promote a pending coding section to active when prior phases finish.

        Starts the per-task timer on the first unsubmitted task when enabled.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the section was activated in this call.
        """
        if not prior_sections_complete_for(interview_id, "coding"):
            return False
        with CodingUnitOfWork(auto_commit=True) as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None or section.status != "pending":
                return False
            updated = section.with_activated()
            current = updated.find_first_unsubmitted()
            if (
                current is not None
                and updated.task_time_limit_seconds is not None
                and current.started_at is None
            ):
                updated = updated.start_timer_for_task(current.id)
            uow.coding_sections.save_aggregate(updated)
            return True

    @staticmethod
    def on_phase_complete(interview_id: str) -> None:
        """Schedule background prefetch of coding section narrative feedback.

        Idempotent: skips when feedback is already cached.

        Args:
            interview_id: Parent interview UUID.
        """
        if not CodingSectionService._should_prefetch_section_feedback(interview_id):
            return
        schedule_feedback_prefetch(
            lambda: CodingSectionService._prefetch_section_feedback(interview_id)
        )

    @staticmethod
    async def ensure_section_feedback(interview_id: str) -> None:
        """Synchronously prefetch section feedback before session completion.

        Idempotent: skips when feedback is already cached or the section is
        incomplete.

        Args:
            interview_id: Parent interview UUID.
        """
        await CodingSectionService._prefetch_section_feedback(interview_id)

    @staticmethod
    def _should_prefetch_section_feedback(interview_id: str) -> bool:
        """Return whether section feedback should be generated for an interview.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the coding section exists, is complete, and lacks feedback.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            return should_prefetch_feedback(section)

    @staticmethod
    async def _prefetch_section_feedback(interview_id: str) -> None:
        """Generate and persist cached coding section feedback.

        Args:
            interview_id: Parent interview UUID.
        """
        await run_feedback_prefetch(
            interview_id,
            section_name="coding",
            should_prefetch=lambda: (
                CodingSectionService._should_prefetch_section_feedback(interview_id)
            ),
            evaluate=lambda provider: CodingSectionService._evaluate_section_feedback(
                interview_id,
                provider,
            ),
            persist=lambda payload, score: (
                CodingSectionService._persist_section_feedback(
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
        """Run the coding section LLM evaluation.

        Args:
            interview_id: Parent interview UUID.
            provider: Configured AI provider instance.

        Returns:
            Feedback payload and section score, or None when evaluation is skipped.
        """
        summary = CodingQueryService.get_evaluation_summary(interview_id)
        if summary is None or not summary.items:
            return None
        section_eval = await CodingEvaluatorService.evaluate_section(
            provider=provider,  # type: ignore[arg-type]
            task_submissions=list(summary.items),
            sources_text=CodingQueryService.sources_text_for_section(interview_id),
            locale=CodingSectionService._section_locale(interview_id),
        )
        return section_eval.model_dump(), summary.score

    @staticmethod
    def _persist_section_feedback(
        interview_id: str,
        payload: dict[str, object],
        score: int,
    ) -> None:
        """Persist prefetched coding section feedback when still absent.

        Args:
            interview_id: Parent interview UUID.
            payload: Section evaluation payload from the LLM.
            score: Earned section score.
        """
        with CodingUnitOfWork(auto_commit=True) as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None or section.section_feedback is not None:
                return
            updated = section.with_cached_section_feedback(
                payload,
                section_score=score,
            )
            uow.coding_sections.save_aggregate(updated)

    @staticmethod
    def _section_locale(interview_id: str) -> str:
        """Load the coding section locale for evaluation prompts.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Locale code, defaulting to ``en`` when the section is missing.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return "en"
            return section.locale
