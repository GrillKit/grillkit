# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Background prefetch of section narrative feedback after phase completion."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from app.ai.base import AIProvider
from app.platform.services.config import ConfigService

logger = logging.getLogger(__name__)

EvaluationPayload = tuple[dict[str, Any], int]


async def prefetch_section_feedback(
    interview_id: str,
    *,
    section_name: str,
    should_prefetch: Callable[[], bool],
    evaluate: Callable[[AIProvider], Awaitable[EvaluationPayload | None]],
    persist: Callable[[dict[str, Any], int], None],
) -> None:
    """Generate and persist cached section feedback when prerequisites are met.

    Args:
        interview_id: Parent interview UUID.
        section_name: Section kind label for log messages (``theory`` or ``coding``).
        should_prefetch: Returns True when feedback should be generated.
        evaluate: Async LLM evaluation returning payload dict and section score.
        persist: Saves feedback payload and section score when evaluation succeeds.
    """
    if not should_prefetch():
        return

    try:
        provider = ConfigService.create_provider_from_config()
    except ValueError:
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
