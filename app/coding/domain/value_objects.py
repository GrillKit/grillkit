# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RunOutcomeStatus = Literal[
    "success",
    "compile_error",
    "runtime_error",
    "time_limit_exceeded",
    "tests_failed",
]


@dataclass(frozen=True, slots=True)
class PlannedCodingTask:
    """Task snapshot used when starting a coding section.

    Attributes:
        id: Unique task identifier from the coding bank.
        text: Localized task prompt shown to the candidate.
        task_spec: Task metadata for persistence, UI, and Judge0 execution.
    """

    id: str
    text: str
    task_spec: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TestCaseRunResult:
    """Outcome of executing one public test case via Judge0.

    Attributes:
        name: Test case identifier from the task bank.
        passed: Whether actual stdout matched the expected output.
        expected_stdout: Expected standard output for the test.
        actual_stdout: Captured standard output from Judge0.
        stderr: Captured standard error, if any.
        compile_output: Compiler output when compilation failed.
        judge0_status_id: Raw Judge0 status identifier.
        judge0_status_description: Human-readable Judge0 status label.
    """

    name: str
    passed: bool
    expected_stdout: str
    actual_stdout: str
    stderr: str | None
    compile_output: str | None
    judge0_status_id: int | None
    judge0_status_description: str | None


@dataclass(frozen=True, slots=True)
class CodingRunResult:
    """Aggregated outcome of a Run action against public tests or compile-only.

    Attributes:
        status: High-level run outcome for the API and persistence layer.
        stdout: Stdout from the last executed case, if any.
        stderr: Stderr from the last executed case, if any.
        compile_output: Compile output from the last executed case, if any.
        tests_passed: Number of public tests that passed.
        tests_total: Number of public tests executed.
        test_results: Per-test details in execution order.
        duration_ms: Total Judge0 wall time across executed cases.
    """

    status: RunOutcomeStatus
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    tests_passed: int
    tests_total: int
    test_results: tuple[TestCaseRunResult, ...]
    duration_ms: int | None
