# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test doubles for Judge0 integration in coding tests."""

from __future__ import annotations

from dataclasses import dataclass

from app.coding.domain.value_objects import CaseRunResult, CodingRunResult


@dataclass(frozen=True, slots=True)
class FakeRunConfig:
    """Configuration for a fake Judge0 run result.

    Attributes:
        status: High-level run outcome (success, compile_error, etc.).
        tests_passed: How many public tests passed.
        tests_total: How many public tests were executed.
        stdout: Last captured stdout.
        stderr: Last captured stderr.
        compile_output: Compile diagnostics.
        duration_ms: Execution duration.
    """

    status: str = "success"
    tests_passed: int = 2
    tests_total: int = 2
    stdout: str | None = "42\n"
    stderr: str | None = None
    compile_output: str | None = None
    duration_ms: int | None = 100


def fake_coding_run_result(config: FakeRunConfig | None = None) -> CodingRunResult:
    """Build a deterministic ``CodingRunResult`` for test doubles.

    Args:
        config: Optional configuration overrides.

    Returns:
        A ``CodingRunResult`` matching the fake Judge0 response shape.
    """
    cfg = config or FakeRunConfig()
    test_results: tuple[CaseRunResult, ...] = (
        CaseRunResult(
            name="test_1",
            passed=True,
            expected_stdout="42",
            actual_stdout="42",
            stderr=None,
            compile_output=None,
            judge0_status_id=3,
            judge0_status_description="Accepted",
        ),
        CaseRunResult(
            name="test_2",
            passed=True,
            expected_stdout="42\n",
            actual_stdout="42\n",
            stderr=None,
            compile_output=None,
            judge0_status_id=3,
            judge0_status_description="Accepted",
        ),
    )
    if cfg.tests_total == 0:
        test_results = ()
    return CodingRunResult(
        status=cfg.status,  # type: ignore[arg-type]
        stdout=cfg.stdout,
        stderr=cfg.stderr,
        compile_output=cfg.compile_output,
        tests_passed=cfg.tests_passed,
        tests_total=cfg.tests_total,
        test_results=test_results,
        duration_ms=cfg.duration_ms,
    )


def fake_compile_error_result(
    compile_output: str = "SyntaxError: invalid syntax",
) -> CodingRunResult:
    """Return a compile-error run result for negative tests.

    Args:
        compile_output: Compiler diagnostic text.

    Returns:
        CodingRunResult with ``compile_error`` status.
    """
    return CodingRunResult(
        status="compile_error",
        stdout=None,
        stderr=None,
        compile_output=compile_output,
        tests_passed=0,
        tests_total=0,
        test_results=(),
        duration_ms=50,
    )


def fake_tests_failed_result(
    expected: str = "42",
    actual: str = "0",
) -> CodingRunResult:
    """Return a tests-failed run result for negative tests.

    Args:
        expected: Expected stdout for the failing test.
        actual: Actual stdout from the run.

    Returns:
        CodingRunResult with ``tests_failed`` status.
    """
    return CodingRunResult(
        status="tests_failed",
        stdout=actual,
        stderr=None,
        compile_output=None,
        tests_passed=0,
        tests_total=2,
        test_results=(
            CaseRunResult(
                name="test_1",
                passed=False,
                expected_stdout=expected,
                actual_stdout=actual,
                stderr=None,
                compile_output=None,
                judge0_status_id=3,
                judge0_status_description="Accepted",
            ),
            CaseRunResult(
                name="test_2",
                passed=True,
                expected_stdout="42",
                actual_stdout="42",
                stderr=None,
                compile_output=None,
                judge0_status_id=3,
                judge0_status_description="Accepted",
            ),
        ),
        duration_ms=120,
    )
