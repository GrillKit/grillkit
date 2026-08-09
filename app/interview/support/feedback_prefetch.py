# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared narrative feedback prefetch workflow for interview sections."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any, Protocol

from app.ai.base import AIProvider
from app.interview.domain.session_phases import SectionEvaluationSummary
from app.interview.domain.value_objects import SectionKind
from app.interview.repositories.uow import InterviewUnitOfWork
from app.platform.domain.config import ConfigService

logger = logging.getLogger(__name__)
EvaluationPayload = tuple[dict[str, Any], int]

PersistFn = Callable[[dict[str, Any], int], None]
EvaluateFn = Callable[[AIProvider], Awaitable[EvaluationPayload | None]]
ShouldPrefetchFn = Callable[[], bool]
EvaluateSectionFn = Callable[
    [object, SectionEvaluationSummary, str, str],
    Awaitable[tuple[dict[str, object], int] | None],
]
GetSectionFn = Callable[[InterviewUnitOfWork, str], Any]
SaveSectionFn = Callable[[InterviewUnitOfWork, Any], None]


async def prefetch_section_feedback(
    interview_id: str,
    *,
    section_name: str,
    should_prefetch: Callable[[], bool],
    evaluate: Callable[[AIProvider], Awaitable[EvaluationPayload | None]],
    persist: Callable[[dict[str, Any], int], None],
) -> None:
    """Generate and persist cached section feedback when prerequisites are met."""
    if not should_prefetch():
        return

    try:
        provider = ConfigService.create_provider_from_config()
    except Exception:
        logger.warning(
            "Skipping %s section prefetch for %s: provider not configured",
            section_name,
            interview_id,
        )
        return

    try:
        result = await evaluate(provider)
    except Exception:
        logger.exception(
            "%s section prefetch failed for interview %s",
            section_name.capitalize(),
            interview_id,
        )
        return

    if result is None:
        return

    payload, score = result
    persist(payload, score)


class SectionFeedbackQuery(Protocol):
    """Minimal query surface needed for section feedback prefetch."""

    def get_evaluation_summary(
        self,
        interview_id: str,
    ) -> SectionEvaluationSummary | None: ...

    def sources_text_for_section(self, interview_id: str) -> str: ...


def should_prefetch_feedback(section: object | None) -> bool:
    """Return whether section narrative feedback should be generated."""
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
    """Schedule background section feedback prefetch when prerequisites pass."""
    asyncio.create_task(run_prefetch())


async def run_feedback_prefetch(
    interview_id: str,
    *,
    section_name: SectionKind,
    should_prefetch: ShouldPrefetchFn,
    evaluate: EvaluateFn,
    persist: PersistFn,
) -> None:
    """Generate and persist cached section feedback when prerequisites are met."""
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
        self._uow = uow
        self._section_name = section_name
        self._build = build
        self._query = query
        self._get_section = get_section
        self._save_section = save_section
        self._evaluate_section = evaluate_section

    def should_prefetch(self, interview_id: str) -> bool:
        """Return whether section feedback should be generated."""
        return should_prefetch_feedback(self._get_section(self._uow, interview_id))

    def on_phase_complete(self, interview_id: str) -> None:
        """Schedule background prefetch when prerequisites are met."""
        if not self.should_prefetch(interview_id):
            return
        schedule_feedback_prefetch(
            lambda: self._run_in_background(
                interview_id,
                build=self._build,
            )
        )

    async def ensure_section_feedback(self, interview_id: str) -> None:
        """Synchronously prefetch section feedback before session completion."""
        await self.prefetch(interview_id)

    async def prefetch(self, interview_id: str) -> None:
        """Generate and persist cached section feedback when prerequisites pass."""
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
        """Run section LLM evaluation for prefetch."""
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
        """Persist prefetched section feedback when still absent."""
        section = self._get_section(self._uow, interview_id)
        if section is None or section.section_feedback is not None:
            return
        updated = section.with_cached_section_feedback(
            payload,
            section_score=score,
        )
        self._save_section(self._uow, updated)

    def _section_locale(self, interview_id: str) -> str:
        """Load the section locale for evaluation prompts."""
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
        """Persist prefetched feedback in a dedicated auto-commit unit of work."""
        with InterviewUnitOfWork(auto_commit=True) as uow:
            self._build(uow).persist(interview_id, payload, score)

    @staticmethod
    async def _run_in_background(
        interview_id: str,
        *,
        build: Callable[[InterviewUnitOfWork], SectionFeedbackPrefetch],
    ) -> None:
        """Run section feedback prefetch in a dedicated unit of work."""
        with InterviewUnitOfWork() as uow:
            await build(uow).prefetch(interview_id)
