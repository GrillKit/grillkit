# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding task planning."""

import pytest

from app.coding.domain.task_spec import (
    client_task_spec_from_stored,
    task_spec_from_bank_task,
)
from app.coding.services.planning import (
    build_coding_task_plan,
    validate_selection,
    validate_task_count,
)
from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.shared.coding import CodingSpec, CodingTask


def test_task_spec_from_bank_task_omits_hidden_tests() -> None:
    """Persisted task spec includes public tests but never hidden tests."""
    from app.shared.coding import CodingTestCase

    task = CodingTask(
        id="algo-001",
        difficulty=2,
        tags=("sorting",),
        text="Sort numbers",
        coding=CodingSpec(
            language="python",
            evaluation_mode="tests",
            starter_code="pass",
            entrypoint="solve",
            public_tests=(
                CodingTestCase(
                    name="normal",
                    stdin="1\n",
                    expected_stdout="1\n",
                ),
            ),
            hidden_tests=(),
        ),
    )
    spec = task_spec_from_bank_task(task)
    assert spec["language"] == "python"
    assert spec["evaluation_mode"] == "tests"
    assert spec["public_tests"] == [
        {"name": "normal", "stdin": "1\n", "expected_stdout": "1\n"}
    ]
    assert spec["hidden_tests"] == []
    client_spec = client_task_spec_from_stored(spec)
    assert "hidden_tests" not in client_spec


def test_build_coding_task_plan_from_bank() -> None:
    """Coding planning loads tasks from the coding bank only."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics",),
            ),
        )
    )
    planned = build_coding_task_plan(selection, task_count=1, locale="en")
    assert len(planned) == 1
    assert planned[0].id.startswith("bas-")
    assert planned[0].task_spec["language"] == "python"


def test_validate_task_count_requires_one_per_topic() -> None:
    """Task count must cover every selected topic."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics", "oop"),
            ),
        )
    )
    with pytest.raises(ValueError, match="at least 2"):
        validate_task_count(selection, 1)


def test_validate_selection_rejects_unknown_track() -> None:
    """Unknown coding track slug raises ValueError."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="unknown",
                level="junior",
                categories=("basics",),
            ),
        )
    )
    with pytest.raises(ValueError, match="Unknown coding track"):
        validate_selection(selection)
