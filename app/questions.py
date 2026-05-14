# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""YAML question loader.

This module provides functionality for loading interview questions
from YAML files organized by language, level, and category.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data" / "questions"


@dataclass
class Question:
    """Interview question data.

    Attributes:
        id: Unique question identifier.
        type: Question type (e.g., "technical", "behavioral").
        difficulty: Difficulty level (1-5 scale).
        tags: List of topic tags.
        text: The question text.
        code: Optional code snippet (None if not applicable).
        follow_ups: List of follow-up questions.
        expected_points: Expected answer key points.
    """

    id: str
    type: str
    difficulty: int
    tags: list[str]
    text: str
    code: str | None
    follow_ups: list[str]
    expected_points: list[str]


def load_category(language: str, level: str, category: str) -> list[Question]:
    """Load questions for a specific category.

    Args:
        language: Programming language (e.g., "python", "javascript").
        level: Difficulty level (e.g., "junior", "middle", "senior").
        category: Question category name (e.g., "basics", "oop").

    Returns:
        List of Question objects. Empty list if file doesn't exist.
    """
    path = DATA_DIR / language / level / f"{category}.yaml"
    if not path.exists():
        return []

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        return []

    questions = []
    for q in data.get("questions", []):
        questions.append(
            Question(
                id=q["id"],
                type=q["type"],
                difficulty=q["difficulty"],
                tags=q.get("tags", []),
                text=q["question"]["text"],
                code=q["question"].get("code"),
                follow_ups=q.get("follow_ups", []),
                expected_points=q.get("expected_points", []),
            )
        )
    return questions


def list_categories(language: str, level: str) -> list[str]:
    """List available categories for a language and level.

    Args:
        language: Programming language (e.g., "python", "javascript").
        level: Difficulty level (e.g., "junior", "middle", "senior").

    Returns:
        List of category names (YAML filenames without extension).
        Empty list if directory doesn't exist.
    """
    path = DATA_DIR / language / level
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.yaml")]
