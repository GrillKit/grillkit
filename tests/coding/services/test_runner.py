# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for CodingRunnerService."""

from unittest.mock import AsyncMock

import pytest

from app.coding.services.judge0_client import (
    JUDGE0_STATUS_ACCEPTED,
    JUDGE0_STATUS_COMPILATION_ERROR,
    Judge0SubmissionResult,
)
from app.coding.services.runner import CodingRunnerService


def _submission(
    *,
    status_id: int,
    stdout: str | None = None,
    stderr: str | None = None,
    compile_output: str | None = None,
) -> Judge0SubmissionResult:
    return Judge0SubmissionResult(
        status_id=status_id,
        status_description="status",
        stdout=stdout,
        stderr=stderr,
        compile_output=compile_output,
        time="0.01",
        memory=1024,
    )


@pytest.mark.asyncio
async def test_run_public_tests_success() -> None:
    """All matching public tests produce a success aggregate status."""
    client = AsyncMock()
    client.submit.return_value = _submission(
        status_id=JUDGE0_STATUS_ACCEPTED,
        stdout="3\n",
    )
    task_spec = {
        "language": "python",
        "evaluation_mode": "tests",
        "entrypoint": "solve",
        "public_tests": [
            {
                "name": "normal",
                "stdin": "1\n2\n",
                "expected_stdout": "3\n",
            }
        ],
    }

    result = await CodingRunnerService.run_public_tests(
        source_code="def solve(a, b):\n    return a + b",
        task_spec=task_spec,
        client=client,
    )

    assert result.status == "success"
    assert result.tests_passed == 1
    assert result.tests_total == 1
    assert result.test_results[0].passed is True


@pytest.mark.asyncio
async def test_run_public_tests_stops_on_first_failure() -> None:
    """Runner short-circuits after the first failing public test."""
    client = AsyncMock()
    client.submit.side_effect = [
        _submission(status_id=JUDGE0_STATUS_ACCEPTED, stdout="1\n"),
        _submission(status_id=JUDGE0_STATUS_ACCEPTED, stdout="wrong\n"),
    ]
    task_spec = {
        "language": "python",
        "evaluation_mode": "tests",
        "entrypoint": "solve",
        "public_tests": [
            {"name": "first", "stdin": "", "expected_stdout": "1\n"},
            {"name": "second", "stdin": "", "expected_stdout": "2\n"},
        ],
    }

    result = await CodingRunnerService.run_public_tests(
        source_code="def solve():\n    return 1",
        task_spec=task_spec,
        client=client,
    )

    assert result.status == "tests_failed"
    assert result.tests_passed == 1
    assert result.tests_total == 2
    assert client.submit.await_count == 2


@pytest.mark.asyncio
async def test_run_compile_only_for_ai_tasks() -> None:
    """AI tasks use compile-only Judge0 submissions."""
    client = AsyncMock()
    client.submit.return_value = _submission(status_id=JUDGE0_STATUS_ACCEPTED)
    task_spec = {
        "language": "python",
        "evaluation_mode": "ai",
        "starter_code": "pass",
    }

    result = await CodingRunnerService.run_public_tests(
        source_code="def process(data):\n    return data",
        task_spec=task_spec,
        client=client,
    )

    assert result.status == "success"
    assert result.tests_total == 0
    client.submit.assert_awaited_once()
    assert client.submit.await_args.kwargs["compile_only"] is True


@pytest.mark.asyncio
async def test_run_public_tests_compile_error() -> None:
    """Compilation errors map to compile_error aggregate status."""
    client = AsyncMock()
    client.submit.return_value = _submission(
        status_id=JUDGE0_STATUS_COMPILATION_ERROR,
        compile_output="SyntaxError",
    )
    task_spec = {
        "language": "python",
        "evaluation_mode": "tests",
        "public_tests": [
            {"name": "only", "stdin": "", "expected_stdout": "1\n"},
        ],
    }

    result = await CodingRunnerService.run_public_tests(
        source_code="def broken(:\n    pass",
        task_spec=task_spec,
        client=client,
    )

    assert result.status == "compile_error"
    assert result.tests_passed == 0
