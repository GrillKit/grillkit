# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for theory and coding section service implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from app.ai.base import AIProvider
from app.interview.services.section_prefetch import prefetch_section_feedback
from app.interview.services.sections import SectionKind

PersistFn = Callable[[dict[str, Any], int], None]
EvaluateFn = Callable[[AIProvider], Awaitable[tuple[dict[str, object], int] | None]]
ShouldPrefetchFn = Callable[[], bool]


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
