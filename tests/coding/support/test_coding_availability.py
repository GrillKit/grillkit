# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding availability checks."""

from unittest.mock import patch

import httpx
import pytest

from app.coding.support.coding_availability import (
    is_coding_available,
    is_coding_available_async,
    is_judge0_healthy,
)


def test_is_coding_available_false_when_disabled(monkeypatch) -> None:
    """CODING_ENABLED=false disables coding regardless of Judge0 health."""
    monkeypatch.setenv("CODING_ENABLED", "false")
    with patch(
        "app.coding.support.coding_availability.is_judge0_healthy", return_value=True
    ):
        assert is_coding_available() is False


def test_is_coding_available_requires_judge0(monkeypatch) -> None:
    """Coding is unavailable when Judge0 health check fails."""
    monkeypatch.setenv("CODING_ENABLED", "true")
    with patch(
        "app.coding.support.coding_availability.is_judge0_healthy", return_value=False
    ):
        assert is_coding_available() is False
    with patch(
        "app.coding.support.coding_availability.is_judge0_healthy", return_value=True
    ):
        assert is_coding_available() is True


@pytest.mark.asyncio
async def test_is_coding_available_async_uses_gateway(monkeypatch) -> None:
    """Async availability delegates to Judge0Gateway.health_check."""
    monkeypatch.setenv("CODING_ENABLED", "true")
    with patch(
        "app.coding.support.coding_availability.is_judge0_healthy_async",
        return_value=True,
    ):
        assert await is_coding_available_async() is True


def test_is_judge0_healthy_handles_connection_errors() -> None:
    """Sync health probe returns False when Judge0 is unreachable."""
    with patch("app.coding.support.coding_availability.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.side_effect = httpx.ConnectError("connection refused")
        assert is_judge0_healthy() is False
