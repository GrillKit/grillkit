# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for section feedback background prefetch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.interview.services.section_prefetch import prefetch_section_feedback


@pytest.mark.asyncio
async def test_prefetch_skips_when_should_prefetch_false() -> None:
    """prefetch_section_feedback exits early when should_prefetch returns False."""
    evaluate = AsyncMock()
    persist = MagicMock()

    await prefetch_section_feedback(
        "iv-1",
        section_name="theory",
        should_prefetch=lambda: False,
        evaluate=evaluate,
        persist=persist,
    )

    evaluate.assert_not_awaited()
    persist.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_skips_when_provider_not_configured() -> None:
    """prefetch_section_feedback logs warning when provider creation fails."""
    evaluate = AsyncMock()
    persist = MagicMock()

    with patch(
        "app.interview.services.section_prefetch.ConfigService.create_provider_from_config",
        side_effect=ValueError("No provider configured"),
    ):
        await prefetch_section_feedback(
            "iv-1",
            section_name="theory",
            should_prefetch=lambda: True,
            evaluate=evaluate,
            persist=persist,
        )

    evaluate.assert_not_awaited()
    persist.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_evaluates_and_persists() -> None:
    """prefetch_section_feedback runs evaluation and saves the result."""
    provider = MagicMock()
    payload = {"section_feedback": "Good work."}
    evaluate = AsyncMock(return_value=(payload, 8))
    persist = MagicMock()

    with patch(
        "app.interview.services.section_prefetch.ConfigService.create_provider_from_config",
        return_value=provider,
    ):
        await prefetch_section_feedback(
            "iv-1",
            section_name="theory",
            should_prefetch=lambda: True,
            evaluate=evaluate,
            persist=persist,
        )

    evaluate.assert_awaited_once_with(provider)
    persist.assert_called_once_with(payload, 8)


@pytest.mark.asyncio
async def test_prefetch_skips_persist_when_result_none() -> None:
    """prefetch_section_feedback skips persist when evaluation returns None."""
    provider = MagicMock()
    evaluate = AsyncMock(return_value=None)
    persist = MagicMock()

    with patch(
        "app.interview.services.section_prefetch.ConfigService.create_provider_from_config",
        return_value=provider,
    ):
        await prefetch_section_feedback(
            "iv-1",
            section_name="theory",
            should_prefetch=lambda: True,
            evaluate=evaluate,
            persist=persist,
        )

    evaluate.assert_awaited_once_with(provider)
    persist.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_handles_evaluation_error_gracefully() -> None:
    """prefetch_section_failure logs but does not raise on evaluation failure."""
    provider = MagicMock()
    evaluate = AsyncMock(side_effect=RuntimeError("LLM failure"))
    persist = MagicMock()

    with patch(
        "app.interview.services.section_prefetch.ConfigService.create_provider_from_config",
        return_value=provider,
    ):
        await prefetch_section_feedback(
            "iv-1",
            section_name="theory",
            should_prefetch=lambda: True,
            evaluate=evaluate,
            persist=persist,
        )

    evaluate.assert_awaited_once_with(provider)
    persist.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_handles_provider_creation_error_gracefully() -> None:
    """prefetch_section_feedback logs but does not raise when provider creation fails."""
    evaluate = AsyncMock()
    persist = MagicMock()

    with patch(
        "app.interview.services.section_prefetch.ConfigService.create_provider_from_config",
        side_effect=Exception("unexpected"),
    ):
        await prefetch_section_feedback(
            "iv-1",
            section_name="coding",
            should_prefetch=lambda: True,
            evaluate=evaluate,
            persist=persist,
        )

    evaluate.assert_not_awaited()
    persist.assert_not_called()
