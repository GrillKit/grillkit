# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding task loading."""

from pathlib import Path

import pytest
import yaml

from app.shared.coding import (
    CodingTask,
    list_categories,
    list_levels,
    list_tracks,
    load_categories,
    load_category,
)


def _write_category_yaml(path: Path, tasks: list[dict]) -> None:
    """Write a minimal coding category YAML file for loader tests.

    Args:
        path: Destination ``.yaml`` file path.
        tasks: Task dicts under the ``tasks`` key.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "category": "Test",
        "track": "python",
        "level": "junior",
        "tasks": tasks,
    }
    with open(path, "w") as f:
        yaml.dump(content, f)


@pytest.fixture
def temp_coding_dir(tmp_path, monkeypatch):
    """Create a temporary coding task bank for loader tests.

    Returns:
        Path to the temporary ``data/coding`` root.
    """
    coding_root = tmp_path / "data" / "coding"
    python_junior_dir = coding_root / "python" / "junior"
    python_junior_dir.mkdir(parents=True)

    algorithms_content = {
        "category": "Algorithms",
        "track": "python",
        "level": "junior",
        "tasks": [
            {
                "id": "algo-001",
                "difficulty": 2,
                "tags": ["sorting"],
                "coding": {
                    "language": "python",
                    "evaluation_mode": "tests",
                    "assignment": "Implement bubble sort for the given input format.",
                    "starter_code": "def bubble_sort(arr):\n    pass",
                    "entrypoint": "bubble_sort",
                    "public_tests": [
                        {
                            "name": "sorted",
                            "stdin": "[3, 1, 2]\n",
                            "expected_stdout": "[1, 2, 3]\n",
                        }
                    ],
                },
                "expected_points": ["Correct sorting"],
            },
            {
                "id": "algo-002",
                "difficulty": 2,
                "tags": ["complexity"],
                "coding": {
                    "language": "python",
                    "evaluation_mode": "ai",
                    "assignment": "Refactor this loop to use enumerate().",
                    "starter_code": "for i in range(len(items)):\n    pass",
                },
            },
        ],
    }
    with open(python_junior_dir / "algorithms.yaml", "w") as f:
        yaml.dump(algorithms_content, f)

    monkeypatch.setattr("app.shared.coding.CODING_DIR", coding_root)
    yield coding_root


class TestCodingTasks:
    """Tests for coding task loading functions."""

    def test_load_category_exists(self, temp_coding_dir) -> None:
        """Load an existing coding category."""
        del temp_coding_dir
        tasks = load_category("python", "junior", "algorithms")

        assert len(tasks) == 2
        task = tasks[0]
        assert isinstance(task, CodingTask)
        assert task.id == "algo-001"
        assert task.difficulty == 2
        assert task.tags == ("sorting",)
        assert task.text == "Implement bubble sort for the given input format."
        assert task.coding.language == "python"
        assert task.coding.evaluation_mode == "tests"
        assert task.coding.entrypoint == "bubble_sort"
        assert len(task.coding.public_tests) == 1
        assert task.coding.public_tests[0].name == "sorted"
        assert task.expected_points == ("Correct sorting",)

    def test_load_category_non_existent(self, temp_coding_dir) -> None:
        """Missing category files return an empty list."""
        del temp_coding_dir
        assert load_category("python", "junior", "missing") == []

    def test_list_tracks(self, temp_coding_dir) -> None:
        """List tracks from the coding bank root."""
        del temp_coding_dir
        assert list_tracks() == ["python"]

    def test_list_levels(self, temp_coding_dir) -> None:
        """List levels for a coding track."""
        del temp_coding_dir
        assert list_levels("python") == ["junior"]

    def test_list_categories(self, temp_coding_dir) -> None:
        """List categories for a track and level."""
        del temp_coding_dir
        assert list_categories("python", "junior") == ["algorithms"]

    def test_load_categories_merges_and_dedupes(self, temp_coding_dir) -> None:
        """load_categories merges YAML files and de-duplicates by id."""
        root = temp_coding_dir
        duplicate = {
            "category": "Dup",
            "track": "python",
            "level": "junior",
            "tasks": [
                {
                    "id": "algo-001",
                    "difficulty": 1,
                    "coding": {
                        "language": "python",
                        "evaluation_mode": "ai",
                        "assignment": "Duplicate task.",
                    },
                },
                {
                    "id": "algo-003",
                    "difficulty": 1,
                    "coding": {
                        "language": "python",
                        "evaluation_mode": "ai",
                        "assignment": "Unique task.",
                    },
                },
            ],
        }
        with open(root / "python" / "junior" / "dup.yaml", "w") as f:
            yaml.dump(duplicate, f)

        tasks = load_categories("python", "junior", ["algorithms", "dup"])
        assert [task.id for task in tasks] == ["algo-001", "algo-002", "algo-003"]

    def test_load_real_python_junior_basics(self) -> None:
        """Load production basics category including type-hints task."""
        tasks = load_category("python", "junior", "basics", locale="en")
        by_id = {task.id: task for task in tasks}
        assert "bas-004" in by_id
        task = by_id["bas-004"]
        assert task.coding.evaluation_mode == "ai"
        assert task.coding.starter_code is not None
        assert "def process" in task.coding.starter_code
        assert "type hints" in task.text.lower()
