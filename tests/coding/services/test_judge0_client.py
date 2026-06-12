# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Judge0 HTTP client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.coding.services.judge0_client import Judge0Client, Judge0SubmissionResult


@pytest.mark.asyncio
async def test_health_check_returns_true_on_200() -> None:
    """Health check succeeds when /about returns HTTP 200."""
    client = Judge0Client(base_url="http://judge0.test")
    response = MagicMock()
    response.status_code = 200
    mock_http = AsyncMock()
    mock_http.get.return_value = response
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch(
        "app.coding.services.judge0_client.httpx.AsyncClient", return_value=mock_http
    ):
        assert await client.health_check() is True


@pytest.mark.asyncio
async def test_health_check_returns_false_on_network_error() -> None:
    """Health check fails closed on transport errors."""
    client = Judge0Client(base_url="http://judge0.test")
    mock_http = AsyncMock()
    mock_http.get.side_effect = httpx.ConnectError("down")
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch(
        "app.coding.services.judge0_client.httpx.AsyncClient", return_value=mock_http
    ):
        assert await client.health_check() is False


@pytest.mark.asyncio
async def test_submit_parses_wait_response() -> None:
    """Submit normalizes a synchronous wait=true submission payload."""
    client = Judge0Client(base_url="http://judge0.test")
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": {"id": 3, "description": "Accepted"},
        "stdout": "3.0\n",
        "stderr": None,
        "compile_output": None,
        "time": "0.01",
        "memory": 4096,
    }
    mock_http = AsyncMock()
    mock_http.post.return_value = response
    mock_http.__aenter__.return_value = mock_http
    mock_http.__aexit__.return_value = None

    with patch(
        "app.coding.services.judge0_client.httpx.AsyncClient", return_value=mock_http
    ):
        result = await client.submit(source_code="print(1)", language_id=71)

    assert result == Judge0SubmissionResult(
        status_id=3,
        status_description="Accepted",
        stdout="3.0\n",
        stderr=None,
        compile_output=None,
        time="0.01",
        memory=4096,
    )
    mock_http.post.assert_awaited_once()
    call_kwargs = mock_http.post.await_args.kwargs
    assert call_kwargs["json"]["language_id"] == 71
    assert call_kwargs["params"]["wait"] == "true"
