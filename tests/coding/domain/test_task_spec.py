# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding task spec builders."""

from app.coding.domain.task_spec import (
    client_task_spec_from_stored,
    task_spec_from_bank_task,
)
from app.shared.coding import CodingSpec, CodingTask, CodingTestCase


def test_task_spec_from_bank_task_builds_correct_spec() -> None:
    """task_spec_from_bank_task builds correct spec with tests and expected_points."""
    task = CodingTask(
        id="algo-001",
        difficulty=2,
        tags=("sorting",),
        text="Sort numbers",
        coding=CodingSpec(
            language="python",
            evaluation_mode="tests",
            starter_code="def solve():\n    pass",
            entrypoint="solve",
            public_tests=(
                CodingTestCase(name="normal", stdin="1\n2\n", expected_stdout="3\n"),
            ),
            hidden_tests=(
                CodingTestCase(name="edge", stdin="0\n", expected_stdout="0\n"),
            ),
            time_limit_seconds=2,
            memory_limit_kb=65536,
        ),
        expected_points=("Handle edge cases", "Use efficient algorithm"),
    )

    spec = task_spec_from_bank_task(task)

    assert spec["language"] == "python"
    assert spec["evaluation_mode"] == "tests"
    assert spec["starter_code"] == "def solve():\n    pass"
    assert spec["entrypoint"] == "solve"
    assert spec["time_limit_seconds"] == 2
    assert spec["memory_limit_kb"] == 65536
    assert spec["public_tests"] == [
        {"name": "normal", "stdin": "1\n2\n", "expected_stdout": "3\n"},
    ]
    assert spec["hidden_tests"] == [
        {"name": "edge", "stdin": "0\n", "expected_stdout": "0\n"},
    ]
    assert spec["expected_points"] == ["Handle edge cases", "Use efficient algorithm"]


def test_task_spec_from_bank_task_with_empty_tests() -> None:
    """task_spec_from_bank_task handles empty test lists."""
    task = CodingTask(
        id="ai-001",
        difficulty=1,
        tags=("open-ended",),
        text="Explain recursion",
        coding=CodingSpec(
            language="python",
            evaluation_mode="ai",
            starter_code="# Your answer here",
            public_tests=(),
            hidden_tests=(),
        ),
        expected_points=(),
    )

    spec = task_spec_from_bank_task(task)

    assert spec["public_tests"] == []
    assert spec["hidden_tests"] == []
    assert spec["expected_points"] == []
    assert "entrypoint" not in spec or spec.get("entrypoint") is None


def test_client_task_spec_from_stored_strips_hidden_tests() -> None:
    """client_task_spec_from_stored removes hidden_tests entirely."""
    stored = {
        "language": "python",
        "evaluation_mode": "tests",
        "starter_code": "pass",
        "public_tests": [
            {"name": "normal", "stdin": "1\n", "expected_stdout": "1\n"},
        ],
        "hidden_tests": [
            {"name": "secret", "stdin": "42\n", "expected_stdout": "42\n"},
        ],
        "expected_points": ["Point 1"],
    }

    client_spec = client_task_spec_from_stored(stored)

    assert "hidden_tests" not in client_spec
    assert client_spec["public_tests"] == [{"name": "normal"}]
    assert client_spec["language"] == "python"
    assert client_spec["evaluation_mode"] == "tests"
    assert client_spec["starter_code"] == "pass"
    assert client_spec["expected_points"] == ["Point 1"]


def test_client_task_spec_from_stored_strips_public_test_details() -> None:
    """client_task_spec_from_stored strips stdin and expected_stdout from public tests."""
    stored = {
        "language": "python",
        "public_tests": [
            {"name": "test1", "stdin": "in1", "expected_stdout": "out1"},
            {"name": "test2", "stdin": "in2", "expected_stdout": "out2"},
        ],
    }

    client_spec = client_task_spec_from_stored(stored)

    for test in client_spec["public_tests"]:
        assert set(test.keys()) == {"name"}
        assert "stdin" not in test
        assert "expected_stdout" not in test


def test_client_task_spec_from_stored_handles_empty_public_tests() -> None:
    """client_task_spec_from_stored handles empty public_tests list."""
    stored = {
        "language": "python",
        "public_tests": [],
        "hidden_tests": [],
    }

    client_spec = client_task_spec_from_stored(stored)

    assert client_spec["public_tests"] == []
    assert "hidden_tests" not in client_spec


def test_client_task_spec_from_stored_handles_missing_public_tests() -> None:
    """client_task_spec_from_stored handles missing public_tests key."""
    stored = {
        "language": "python",
    }

    client_spec = client_task_spec_from_stored(stored)

    assert "public_tests" not in client_spec


def test_client_task_spec_from_stored_preserves_other_fields() -> None:
    """client_task_spec_from_stored preserves non-test-related fields."""
    stored = {
        "language": "python",
        "evaluation_mode": "ai",
        "starter_code": "# code",
        "entrypoint": None,
        "time_limit_seconds": 5,
        "memory_limit_kb": 1024,
        "custom_field": "custom_value",
    }

    client_spec = client_task_spec_from_stored(stored)

    assert client_spec["language"] == "python"
    assert client_spec["evaluation_mode"] == "ai"
    assert client_spec["starter_code"] == "# code"
    assert client_spec["entrypoint"] is None
    assert client_spec["time_limit_seconds"] == 5
    assert client_spec["memory_limit_kb"] == 1024
    assert client_spec["custom_field"] == "custom_value"
