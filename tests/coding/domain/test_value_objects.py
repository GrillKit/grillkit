# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding domain value objects."""

from dataclasses import FrozenInstanceError

import pytest

from app.coding.domain.value_objects import (
    CodingRunResult,
    PlannedCodingTask,
    RunOutcomeStatus,
    TestCaseRunResult,
)


class TestPlannedCodingTask:
    """Tests for the ``PlannedCodingTask`` frozen dataclass."""

    def test_planned_coding_task_creation(self) -> None:
        """PlannedCodingTask can be constructed and fields are accessible."""
        task = PlannedCodingTask(
            id="cod-001",
            text="Write a function.",
            task_spec={"language": "python"},
        )
        assert task.id == "cod-001"
        assert task.text == "Write a function."
        assert task.task_spec == {"language": "python"}

    def test_planned_coding_task_is_frozen(self) -> None:
        """PlannedCodingTask is immutable after creation."""
        task = PlannedCodingTask(
            id="cod-001",
            text="Write a function.",
            task_spec={},
        )
        with pytest.raises(FrozenInstanceError):
            task.id = "cod-002"  # type: ignore[misc]


class TestTestCaseRunResult:
    """Tests for the ``TestCaseRunResult`` frozen dataclass."""

    def test_test_case_run_result_creation(self) -> None:
        """TestCaseRunResult can be constructed with all fields."""
        result = TestCaseRunResult(
            name="normal",
            passed=True,
            expected_stdout="1\n",
            actual_stdout="1\n",
            stderr=None,
            compile_output=None,
            judge0_status_id=3,
            judge0_status_description="Accepted",
        )
        assert result.name == "normal"
        assert result.passed is True
        assert result.expected_stdout == "1\n"
        assert result.judge0_status_id == 3

    def test_test_case_run_result_is_frozen(self) -> None:
        """TestCaseRunResult is immutable after creation."""
        result = TestCaseRunResult(
            name="normal",
            passed=True,
            expected_stdout="",
            actual_stdout="",
            stderr=None,
            compile_output=None,
            judge0_status_id=None,
            judge0_status_description=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.passed = False  # type: ignore[misc]


class TestCodingRunResult:
    """Tests for the ``CodingRunResult`` frozen dataclass."""

    def test_coding_run_result_creation(self) -> None:
        """CodingRunResult can be constructed with all fields."""
        test_result = TestCaseRunResult(
            name="normal",
            passed=True,
            expected_stdout="1\n",
            actual_stdout="1\n",
            stderr=None,
            compile_output=None,
            judge0_status_id=3,
            judge0_status_description="Accepted",
        )
        result = CodingRunResult(
            status="success",  # type: ignore[arg-type]
            stdout="1\n",
            stderr=None,
            compile_output=None,
            tests_passed=1,
            tests_total=1,
            test_results=(test_result,),
            duration_ms=120,
        )
        assert result.status == "success"
        assert result.tests_passed == 1
        assert result.tests_total == 1
        assert len(result.test_results) == 1
        assert result.test_results[0].name == "normal"
        assert result.duration_ms == 120

    def test_coding_run_result_is_frozen(self) -> None:
        """CodingRunResult is immutable after creation."""
        result = CodingRunResult(
            status="success",  # type: ignore[arg-type]
            stdout=None,
            stderr=None,
            compile_output=None,
            tests_passed=0,
            tests_total=0,
            test_results=(),
            duration_ms=None,
        )
        with pytest.raises(FrozenInstanceError):
            result.tests_passed = 1  # type: ignore[misc]

    def test_coding_run_result_with_empty_test_results(self) -> None:
        """CodingRunResult works with empty test results."""
        result = CodingRunResult(
            status="compile_error",  # type: ignore[arg-type]
            stdout=None,
            stderr=None,
            compile_output="SyntaxError",
            tests_passed=0,
            tests_total=0,
            test_results=(),
            duration_ms=None,
        )
        assert result.status == "compile_error"
        assert result.test_results == ()
