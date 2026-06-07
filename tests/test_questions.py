# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for question loading."""

from pathlib import Path

import pytest
import yaml

from app.questions import (
    Question,
    list_categories,
    list_levels,
    list_tracks,
    load_categories,
    load_category,
)


def _write_category_yaml(path: Path, questions: list[dict]) -> None:
    """Write a minimal category YAML file for loader tests.

    Args:
        path: Destination ``.yaml`` file path.
        questions: Question dicts under the ``questions`` key.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "category": "Test",
        "track": "python",
        "level": "junior",
        "questions": questions,
    }
    with open(path, "w") as f:
        yaml.dump(content, f)


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
        "track": "python",
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
            },
        ],
    }
    with open(python_junior_dir / "data-structures.yaml", "w") as f:
        yaml.dump(ds_content, f)

    # algorithms.yaml
    algo_content = {
        "category": "Algorithms",
        "track": "python",
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
            },
        ],
    }
    with open(python_junior_dir / "algorithms.yaml", "w") as f:
        yaml.dump(algo_content, f)

    # system-design.yaml (senior level)
    sd_content = {
        "category": "System Design",
        "track": "python",
        "level": "senior",
        "description": "Designing scalable systems",
        "questions": [
            {
                "id": "sd-001",
                "type": "scenario",
                "difficulty": 4,
                "tags": ["scalability", "database"],
                "question": {"text": "Design a URL shortener.", "code": None},
            },
        ],
    }
    with open(python_senior_dir / "system-design.yaml", "w") as f:
        yaml.dump(sd_content, f)

    # basics.yaml (javascript)
    js_basics_content = {
        "category": "Basics",
        "track": "javascript",
        "level": "junior",
        "description": "JavaScript fundamentals",
        "questions": [
            {
                "id": "js-001",
                "type": "knowledge",
                "difficulty": 1,
                "tags": ["variables"],
                "question": {"text": "Explain var, let, and const.", "code": None},
            },
        ],
    }
    with open(javascript_junior_dir / "basics.yaml", "w") as f:
        yaml.dump(js_basics_content, f)

    monkeypatch.setattr("app.questions.QUESTIONS_DIR", questions_root)

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

    def test_load_category_non_existent(self, temp_questions_dir):
        """Test loading a non-existent category returns an empty list."""
        questions = load_category("python", "junior", "non-existent")
        assert len(questions) == 0

    def test_load_category_no_questions_key(self, temp_questions_dir):
        """Test loading a category file with no 'questions' key."""
        (temp_questions_dir / "python" / "junior").mkdir(parents=True, exist_ok=True)
        empty_content = {"category": "Empty", "track": "python", "level": "junior"}
        with open(temp_questions_dir / "python" / "junior" / "empty.yaml", "w") as f:
            yaml.dump(empty_content, f)

        questions = load_category("python", "junior", "empty")
        assert len(questions) == 0

    def test_list_tracks(self, temp_questions_dir):
        """Test listing tracks from the question bank root."""
        tracks = list_tracks()
        assert sorted(tracks) == sorted(["javascript", "python"])

    def test_list_levels(self, temp_questions_dir):
        """Test listing levels for a track."""
        levels = list_levels("python")
        assert sorted(levels) == sorted(["junior", "senior"])

    def test_list_categories_exists(self, temp_questions_dir):
        """Test listing categories for an existing track and level."""
        categories = list_categories("python", "junior")
        assert sorted(categories) == sorted(["data-structures", "algorithms"])

    def test_list_categories_non_existent_level(self, temp_questions_dir):
        """Test listing categories for a non-existent level returns empty list."""
        categories = list_categories("python", "expert")
        assert categories == []

    def test_list_categories_non_existent_track(self, temp_questions_dir):
        """Test listing categories for a non-existent track returns empty list."""
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
            "track": "python",
            "level": "junior",
            "questions": [
                {
                    "id": "mq-001",
                    "type": "knowledge",
                    "difficulty": 1,
                    "question": {"text": "Q1"},
                },
                {
                    "id": "mq-002",
                    "type": "coding",
                    "difficulty": 2,
                    "question": {"text": "Q2"},
                },
            ],
        }
        with open(temp_questions_dir / "python" / "junior" / "multi.yaml", "w") as f:
            yaml.dump(multi_q_content, f)

        questions = load_category("python", "junior", "multi")
        assert len(questions) == 2
        assert questions[0].id == "mq-001"
        assert questions[1].id == "mq-002"

    def test_load_categories_merges_and_dedupes(self, temp_questions_dir):
        """load_categories merges multiple YAML files and de-duplicates by id."""
        questions = load_categories(
            "python", "junior", ["data-structures", "algorithms"]
        )
        ids = {q.id for q in questions}
        assert "ds-001" in ids
        assert "algo-001" in ids
        assert len(questions) == len(ids)


class TestQuestionLocalization:
    """Tests for multilingual question text in YAML banks."""

    @pytest.fixture
    def i18n_questions_dir(self, tmp_path, monkeypatch):
        """Temporary question bank with localized and legacy entries.

        Returns:
            Path: Root of the patched ``QUESTIONS_DIR``.
        """
        questions_root = tmp_path / "data" / "questions"
        junior_dir = questions_root / "python" / "junior"
        _write_category_yaml(
            junior_dir / "i18n.yaml",
            [
                {
                    "id": "i18n-001",
                    "type": "knowledge",
                    "difficulty": 1,
                    "tags": ["locale"],
                    "question": {
                        "text": {
                            "en": "English question text.",
                            "ru": "Русский текст вопроса.",
                        },
                        "code": "x = 1",
                    },
                },
                {
                    "id": "i18n-002",
                    "type": "knowledge",
                    "difficulty": 1,
                    "question": {
                        "text": {"en": "English only question."},
                        "code": None,
                    },
                },
                {
                    "id": "legacy-001",
                    "type": "knowledge",
                    "difficulty": 1,
                    "question": {"text": "Legacy plain string question.", "code": None},
                },
            ],
        )
        monkeypatch.setattr("app.questions.QUESTIONS_DIR", questions_root)
        return questions_root

    def test_load_resolves_requested_locale(self, i18n_questions_dir):
        """Localized maps return text for the requested locale."""
        questions = load_category("python", "junior", "i18n", locale="ru")
        by_id = {q.id: q for q in questions}

        q = by_id["i18n-001"]
        assert q.text == "Русский текст вопроса."
        assert q.code == "x = 1"

    def test_load_normalizes_locale_code(self, i18n_questions_dir):
        """Locale codes are normalized before lookup (e.g. ``RU`` → ``ru``)."""
        questions = load_category("python", "junior", "i18n", locale=" RU ")
        assert questions[0].text == "Русский текст вопроса."

    def test_missing_locale_falls_back_to_english(self, i18n_questions_dir):
        """Missing translation falls back to ``en`` for question text."""
        questions = load_category("python", "junior", "i18n", locale="fr")
        by_id = {q.id: q for q in questions}

        assert by_id["i18n-001"].text == "English question text."
        assert by_id["i18n-002"].text == "English only question."

    def test_legacy_plain_string_text(self, i18n_questions_dir):
        """Plain-string ``question.text`` is accepted as English for any locale."""
        for locale in ("en", "ru", "de"):
            questions = load_category("python", "junior", "i18n", locale=locale)
            legacy = next(q for q in questions if q.id == "legacy-001")
            assert legacy.text == "Legacy plain string question."

    def test_code_not_localized(self, i18n_questions_dir):
        """``question.code`` is shared across locales."""
        en = load_category("python", "junior", "i18n", locale="en")[0]
        ru = load_category("python", "junior", "i18n", locale="ru")[0]
        assert en.code == ru.code == "x = 1"

    def test_text_map_without_en_raises_on_fallback(self, i18n_questions_dir):
        """Locale map without ``en`` raises when the requested locale is missing."""
        path = i18n_questions_dir / "python" / "junior" / "bad-text.yaml"
        _write_category_yaml(
            path,
            [
                {
                    "id": "bad-001",
                    "type": "knowledge",
                    "difficulty": 1,
                    "question": {"text": {"ru": "Только русский."}, "code": None},
                },
            ],
        )
        questions_ru = load_category("python", "junior", "bad-text", locale="ru")
        assert questions_ru[0].text == "Только русский."

        with pytest.raises(ValueError, match="bad-001"):
            load_category("python", "junior", "bad-text", locale="en")

    def test_invalid_text_shape_raises(self, i18n_questions_dir):
        """Non-string, non-map ``question.text`` raises ``ValueError``."""
        path = i18n_questions_dir / "python" / "junior" / "bad-shape.yaml"
        _write_category_yaml(
            path,
            [
                {
                    "id": "bad-002",
                    "type": "knowledge",
                    "difficulty": 1,
                    "question": {"text": 42, "code": None},
                },
            ],
        )
        with pytest.raises(ValueError, match="bad-002"):
            load_category("python", "junior", "bad-shape")

    def test_python_junior_basics_bank_russian(self):
        """Migrated pilot bank serves Russian text for ``locale=ru``."""
        questions = load_category("python", "junior", "basics", locale="ru")
        assert questions
        assert any(any("\u0400" <= ch <= "\u04ff" for ch in q.text) for q in questions)
