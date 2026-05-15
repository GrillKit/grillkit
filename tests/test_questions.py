# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for question loading."""

import pytest
import yaml

from app.questions import Question, list_categories, load_category


@pytest.fixture
def temp_questions_dir(tmp_path, monkeypatch):
    """Fixture to create a temporary questions directory structure.

    Returns:
        Path: The path to the temporary questions directory.
    """
    questions_root = tmp_path / "data" / "questions"
    python_junior_dir = questions_root / "python" / "junior"
    python_junior_dir.mkdir(parents=True)

    python_senior_dir = questions_root / "python" / "senior"
    python_senior_dir.mkdir(parents=True)

    javascript_junior_dir = questions_root / "javascript" / "junior"
    javascript_junior_dir.mkdir(parents=True)

    # data-structures.yaml
    ds_content = {
        "category": "Data Structures",
        "language": "python",
        "level": "junior",
        "description": "Fundamental Python data structures and their usage",
        "questions": [
            {
                "id": "ds-001",
                "type": "knowledge",
                "difficulty": 1,
                "tags": ["list", "tuple"],
                "question": {
                    "text": "What is the difference between a list and a tuple?",
                    "code": None,
                },
                "follow_ups": ["When would you choose a tuple over a list?"],
                "expected_points": ["Lists are mutable, tuples are immutable"],
            },
        ],
    }
    with open(python_junior_dir / "data-structures.yaml", "w") as f:
        yaml.dump(ds_content, f)

    # algorithms.yaml
    algo_content = {
        "category": "Algorithms",
        "language": "python",
        "level": "junior",
        "description": "Basic algorithms and their implementation",
        "questions": [
            {
                "id": "algo-001",
                "type": "coding",
                "difficulty": 2,
                "tags": ["sorting", "array"],
                "question": {
                    "text": "Implement bubble sort.",
                    "code": "def bubble_sort(arr):\n    pass",
                },
                "follow_ups": [],
                "expected_points": [],
            },
        ],
    }
    with open(python_junior_dir / "algorithms.yaml", "w") as f:
        yaml.dump(algo_content, f)

    # system-design.yaml (senior level)
    sd_content = {
        "category": "System Design",
        "language": "python",
        "level": "senior",
        "description": "Designing scalable systems",
        "questions": [
            {
                "id": "sd-001",
                "type": "scenario",
                "difficulty": 4,
                "tags": ["scalability", "database"],
                "question": {"text": "Design a URL shortener.", "code": None},
                "follow_ups": [],
                "expected_points": [],
            },
        ],
    }
    with open(python_senior_dir / "system-design.yaml", "w") as f:
        yaml.dump(sd_content, f)

    # basics.yaml (javascript)
    js_basics_content = {
        "category": "Basics",
        "language": "javascript",
        "level": "junior",
        "description": "JavaScript fundamentals",
        "questions": [
            {
                "id": "js-001",
                "type": "knowledge",
                "difficulty": 1,
                "tags": ["variables"],
                "question": {"text": "Explain var, let, and const.", "code": None},
                "follow_ups": [],
                "expected_points": [],
            },
        ],
    }
    with open(javascript_junior_dir / "basics.yaml", "w") as f:
        yaml.dump(js_basics_content, f)

    monkeypatch.setattr("app.questions.DATA_DIR", questions_root)

    yield questions_root


class TestQuestions:
    """Tests for question loading functions."""

    def test_load_category_exists(self, temp_questions_dir):
        """Test loading an existing category."""
        questions = load_category("python", "junior", "data-structures")

        assert len(questions) == 1
        q = questions[0]
        assert isinstance(q, Question)
        assert q.id == "ds-001"
        assert q.type == "knowledge"
        assert q.difficulty == 1
        assert q.tags == ["list", "tuple"]
        assert q.text == "What is the difference between a list and a tuple?"
        assert q.code is None
        assert q.follow_ups == ["When would you choose a tuple over a list?"]
        assert q.expected_points == ["Lists are mutable, tuples are immutable"]

    def test_load_category_non_existent(self, temp_questions_dir):
        """Test loading a non-existent category returns an empty list."""
        questions = load_category("python", "junior", "non-existent")
        assert len(questions) == 0

    def test_load_category_no_questions_key(self, temp_questions_dir):
        """Test loading a category file with no 'questions' key."""
        (temp_questions_dir / "python" / "junior").mkdir(parents=True, exist_ok=True)
        empty_content = {"category": "Empty", "language": "python", "level": "junior"}
        with open(temp_questions_dir / "python" / "junior" / "empty.yaml", "w") as f:
            yaml.dump(empty_content, f)

        questions = load_category("python", "junior", "empty")
        assert len(questions) == 0

    def test_list_categories_exists(self, temp_questions_dir):
        """Test listing categories for an existing language and level."""
        categories = list_categories("python", "junior")
        assert sorted(categories) == sorted(["data-structures", "algorithms"])

    def test_list_categories_non_existent_level(self, temp_questions_dir):
        """Test listing categories for a non-existent level returns empty list."""
        categories = list_categories("python", "expert")
        assert categories == []

    def test_list_categories_non_existent_language(self, temp_questions_dir):
        """Test listing categories for a non-existent language returns empty list."""
        categories = list_categories("java", "junior")
        assert categories == []

    def test_load_category_with_code(self, temp_questions_dir):
        """Test loading a question with a code snippet."""
        questions = load_category("python", "junior", "algorithms")
        assert len(questions) == 1
        q = questions[0]
        assert q.id == "algo-001"
        assert q.code == "def bubble_sort(arr):\n    pass"

    def test_load_category_multiple_questions(self, temp_questions_dir):
        """Test loading a category file with multiple questions."""
        (temp_questions_dir / "python" / "junior").mkdir(parents=True, exist_ok=True)
        multi_q_content = {
            "category": "Multi Question",
            "language": "python",
            "level": "junior",
            "questions": [
                {
                    "id": "mq-001",
                    "type": "knowledge",
                    "difficulty": 1,
                    "question": {"text": "Q1"},
                    "follow_ups": [],
                    "expected_points": [],
                },
                {
                    "id": "mq-002",
                    "type": "coding",
                    "difficulty": 2,
                    "question": {"text": "Q2"},
                    "follow_ups": [],
                    "expected_points": [],
                },
            ],
        }
        with open(temp_questions_dir / "python" / "junior" / "multi.yaml", "w") as f:
            yaml.dump(multi_q_content, f)

        questions = load_category("python", "junior", "multi")
        assert len(questions) == 2
        assert questions[0].id == "mq-001"
        assert questions[1].id == "mq-002"
