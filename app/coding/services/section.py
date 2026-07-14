# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section orchestration service."""

from __future__ import annotations

from typing import ClassVar, Literal

from app.coding.services.evaluator.service import CodingEvaluatorService
from app.coding.services.query import CodingQueryService
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.section_service_support import SectionFeedbackPrefetch
from app.interview.services.sections import (
    SectionEvaluationSummary,
    SectionPageContext,
    prior_sections_complete_for,
)


async def _evaluate_coding_section_feedback(
    provider: object,
    summary: SectionEvaluationSummary,
    sources_text: str,
    locale: str,
) -> tuple[dict[str, object], int] | None:
    """Run the coding section LLM evaluation for prefetch.

    Args:
        provider: Configured AI provider instance.
        summary: Section evaluation summary with per-task rows.
        sources_text: Human-readable selection summary.
        locale: Section locale for prompts.

    Returns:
        Feedback payload and section score.
    """
    section_eval = await CodingEvaluatorService.evaluate_section(
        provider=provider,  # type: ignore[arg-type]
        task_submissions=list(summary.items),
        sources_text=sources_text,
        locale=locale,
    )
    return section_eval.model_dump(), summary.score


def _build_coding_feedback_prefetch(
    uow: InterviewUnitOfWork,
    query: CodingQueryService | None = None,
) -> SectionFeedbackPrefetch:
    """Build coding section feedback prefetch helpers for a unit of work.

    Args:
        uow: Active application unit of work.
        query: Optional query helper sharing the same unit of work.

    Returns:
        Configured prefetch helper for coding sections.
    """
    resolved_query = query or CodingQueryService(uow)
    return SectionFeedbackPrefetch(
        uow,
        section_name="coding",
        build=lambda scoped_uow: _build_coding_feedback_prefetch(scoped_uow),
        query=resolved_query,
        get_section=lambda scoped_uow, interview_id: (
            scoped_uow.coding_sections.get_aggregate(interview_id)
        ),
        save_section=lambda scoped_uow, section: (
            scoped_uow.coding_sections.save_aggregate(section)
        ),
        evaluate_section=_evaluate_coding_section_feedback,
    )


class CodingSectionService:
    """Coding section lifecycle hooks and read helpers."""

    section_kind: ClassVar[Literal["coding"]] = "coding"

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        query: CodingQueryService | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this section scope.
            query: Optional coding query helper sharing the same unit of work.
        """
        self._uow = uow
        self._query = query or CodingQueryService(uow)
        self._feedback = _build_coding_feedback_prefetch(uow, self._query)

    def is_complete(self, interview_id: str) -> bool:
        """Return whether all coding tasks in the section are submitted.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when every task has submitted code or the section was skipped.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            return False
        if section.status in {"skipped", "completed"}:
            return True
        return section.is_complete()

    def is_user_facing(self, interview_id: str) -> bool:
        """Return whether the user should interact with the coding section now.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the coding section is active and still has work remaining.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            return False
        complete = section.status in {"skipped", "completed"} or section.is_complete()
        return section.status == "active" and not complete

    def activate_if_pending(self, interview_id: str) -> bool:
        """Promote a pending coding section to active when prior phases finish.

        Starts the per-task timer on the first unsubmitted task when enabled.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the section was activated in this call.
        """
        return self.activate_pending(interview_id)

    def get_page_context(self, interview_id: str) -> SectionPageContext | None:
        """Return coding section page metadata for session composition.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section page context, or None when no coding section exists.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            return None
        complete = section.status in {"skipped", "completed"} or section.is_complete()
        active = section.status == "active" and not complete
        return SectionPageContext(
            section="coding",
            active=active,
            complete=complete,
        )

    def get_evaluation_summary(
        self,
        interview_id: str,
    ) -> SectionEvaluationSummary | None:
        """Return coding evaluation summary for session completion.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section summary, or None when no coding section exists.
        """
        return self._query.get_evaluation_summary(interview_id)

    def activate_pending(self, interview_id: str) -> bool:
        """Promote a pending coding section to active when prior phases finish.

        Starts the per-task timer on the first unsubmitted task when enabled.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the section was activated in this call.
        """
        if not prior_sections_complete_for(interview_id, "coding", self._uow):
            return False
        section = self._uow.coding_sections.get_aggregate(interview_id)
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
        self._uow.coding_sections.save_aggregate(updated)
        return True

    def on_phase_complete(self, interview_id: str) -> None:
        """Schedule background prefetch of coding section narrative feedback.

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
