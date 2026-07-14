# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for theory and coding section service implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Protocol

from app.ai.base import AIProvider
from app.interview.domain.value_objects import SectionKind
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.section_prefetch import prefetch_section_feedback
from app.interview.services.sections import SectionEvaluationSummary

PersistFn = Callable[[dict[str, Any], int], None]
EvaluateFn = Callable[[AIProvider], Awaitable[tuple[dict[str, object], int] | None]]
ShouldPrefetchFn = Callable[[], bool]
EvaluateSectionFn = Callable[
    [object, SectionEvaluationSummary, str, str],
    Awaitable[tuple[dict[str, object], int] | None],
]
GetSectionFn = Callable[[InterviewUnitOfWork, str], Any]
SaveSectionFn = Callable[[InterviewUnitOfWork, Any], None]


class SectionFeedbackQuery(Protocol):
    """Minimal query surface needed for section feedback prefetch."""

    def get_evaluation_summary(
        self,
        interview_id: str,
    ) -> SectionEvaluationSummary | None: ...

    def sources_text_for_section(self, interview_id: str) -> str: ...


def should_prefetch_feedback(section: object | None) -> bool:
    """Return whether section narrative feedback should be generated.

    Args:
        section: Loaded section aggregate, if any.

    Returns:
        True when the section is complete and feedback is not cached yet.
    """
    if section is None:
        return False
    if getattr(section, "section_feedback", None) is not None:
        return False
    is_complete = getattr(section, "is_complete", None)
    if not callable(is_complete):
        return False
    return bool(is_complete())


def schedule_feedback_prefetch(
    run_prefetch: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Schedule background section feedback prefetch when prerequisites pass.

    Args:
        run_prefetch: Coroutine factory for the prefetch workflow.
    """
    asyncio.create_task(run_prefetch())


async def run_feedback_prefetch(
    interview_id: str,
    *,
    section_name: SectionKind,
    should_prefetch: ShouldPrefetchFn,
    evaluate: EvaluateFn,
    persist: PersistFn,
) -> None:
    """Generate and persist cached section feedback when prerequisites are met.

    Args:
        interview_id: Parent interview UUID.
        section_name: Section kind label for log messages.
        should_prefetch: Returns True when feedback should be generated.
        evaluate: Async LLM evaluation returning payload dict and section score.
        persist: Saves feedback payload and section score when evaluation succeeds.
    """
    await prefetch_section_feedback(
        interview_id,
        section_name=section_name,
        should_prefetch=should_prefetch,
        evaluate=evaluate,
        persist=persist,
    )


class SectionFeedbackPrefetch:
    """Shared narrative feedback prefetch workflow for a section kind."""

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        *,
        section_name: SectionKind,
        build: Callable[[InterviewUnitOfWork], SectionFeedbackPrefetch],
        query: SectionFeedbackQuery,
        get_section: GetSectionFn,
        save_section: SaveSectionFn,
        evaluate_section: EvaluateSectionFn,
    ) -> None:
        """Initialize prefetch helpers bound to one unit of work.

        Args:
            uow: Active application unit of work.
            section_name: Section kind label for log messages.
            build: Factory that rebuilds this helper for background scopes.
            query: Section query service with evaluation summary helpers.
            get_section: Load a section aggregate for an interview.
            save_section: Persist an updated section aggregate.
            evaluate_section: Run the section LLM evaluation workflow.
        """
        self._uow = uow
        self._section_name = section_name
        self._build = build
        self._query = query
        self._get_section = get_section
        self._save_section = save_section
        self._evaluate_section = evaluate_section

    def should_prefetch(self, interview_id: str) -> bool:
        """Return whether section feedback should be generated.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            True when the section exists, is complete, and lacks feedback.
        """
        return should_prefetch_feedback(self._get_section(self._uow, interview_id))

    def on_phase_complete(self, interview_id: str) -> None:
        """Schedule background prefetch when prerequisites are met.

        Args:
            interview_id: Parent interview UUID.
        """
        if not self.should_prefetch(interview_id):
            return
        schedule_feedback_prefetch(
            lambda: SectionFeedbackPrefetch._run_in_background(
                interview_id,
                build=self._build,
            )
        )

    async def ensure_section_feedback(self, interview_id: str) -> None:
        """Synchronously prefetch section feedback before session completion.

        Args:
            interview_id: Parent interview UUID.
        """
        await self.prefetch(interview_id)

    async def prefetch(self, interview_id: str) -> None:
        """Generate and persist cached section feedback when prerequisites pass.

        Args:
            interview_id: Parent interview UUID.
        """
        await run_feedback_prefetch(
            interview_id,
            section_name=self._section_name,
            should_prefetch=lambda: self.should_prefetch(interview_id),
            evaluate=lambda provider: self._evaluate(interview_id, provider),
            persist=lambda payload, score: self._persist_in_background(
                interview_id,
                payload,
                score,
            ),
        )

    async def _evaluate(
        self,
        interview_id: str,
        provider: object,
    ) -> tuple[dict[str, object], int] | None:
        """Run section LLM evaluation for prefetch.

        Args:
            interview_id: Parent interview UUID.
            provider: Configured AI provider instance.

        Returns:
            Feedback payload and section score, or None when skipped.
        """
        summary = self._query.get_evaluation_summary(interview_id)
        if summary is None or not summary.items:
            return None
        return await self._evaluate_section(
            provider,
            summary,
            self._query.sources_text_for_section(interview_id),
            self._section_locale(interview_id),
        )

    def persist(
        self, interview_id: str, payload: dict[str, object], score: int
    ) -> None:
        """Persist prefetched section feedback when still absent.

        Args:
            interview_id: Parent interview UUID.
            payload: Section evaluation payload from the LLM.
            score: Earned section score.
        """
        section = self._get_section(self._uow, interview_id)
        if section is None or section.section_feedback is not None:
            return
        updated = section.with_cached_section_feedback(
            payload,
            section_score=score,
        )
        self._save_section(self._uow, updated)

    def _section_locale(self, interview_id: str) -> str:
        """Load the section locale for evaluation prompts.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Locale code, defaulting to ``en`` when the section is missing.
        """
        section = self._get_section(self._uow, interview_id)
        if section is None:
            return "en"
        return str(section.locale)

    def _persist_in_background(
        self,
        interview_id: str,
        payload: dict[str, object],
        score: int,
    ) -> None:
        """Persist prefetched feedback in a dedicated auto-commit unit of work.

        Args:
            interview_id: Parent interview UUID.
            payload: Section evaluation payload from the LLM.
            score: Earned section score.
        """
        with InterviewUnitOfWork(auto_commit=True) as uow:
            self._build(uow).persist(interview_id, payload, score)

    @staticmethod
    async def _run_in_background(
        interview_id: str,
        *,
        build: Callable[[InterviewUnitOfWork], SectionFeedbackPrefetch],
    ) -> None:
        """Run section feedback prefetch in a dedicated unit of work.

        Args:
            interview_id: Parent interview UUID.
            build: Factory that rebuilds the prefetch helper for the scope.
        """
        with InterviewUnitOfWork() as uow:
            await build(uow).prefetch(interview_id)
