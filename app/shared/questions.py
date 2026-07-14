# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""YAML question loader.

This module provides functionality for loading interview questions
from YAML files organized by track, level, and category.
"""

from dataclasses import dataclass
import logging
from typing import Any

import yaml

from app.shared.locales import DEFAULT_LOCALE, normalize_locale
from app.shared.paths import QUESTIONS_DIR

logger = logging.getLogger(__name__)


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
        expected_points: Rubric bullets for AI evaluation.
    """

    id: str
    type: str
    difficulty: int
    tags: list[str]
    text: str
    code: str | None
    expected_points: tuple[str, ...] = ()


def _resolve_localized_string(
    value: Any,
    locale: str,
    *,
    field: str,
    question_id: str,
) -> str:
    """Return localized string from a plain string or locale map.

    Args:
        value: Plain string (legacy) or ``{locale: text}`` map with required ``en``.
        locale: Requested locale code.
        field: Field name for warning logs (e.g. ``text``).
        question_id: Question id for warning logs.

    Returns:
        Resolved string for the locale, falling back to ``en``.

    Raises:
        ValueError: If value shape is invalid or ``en`` is missing.
    """
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        msg = f"Question {question_id}: invalid {field} (expected str or locale map)"
        raise ValueError(msg)
    code = normalize_locale(locale)
    if code in value and value[code]:
        return str(value[code])
    if DEFAULT_LOCALE not in value or not value[DEFAULT_LOCALE]:
        msg = f"Question {question_id}: missing required '{DEFAULT_LOCALE}' in {field}"
        raise ValueError(msg)
    if code != DEFAULT_LOCALE:
        logger.warning(
            "Question %s: no %s for %s, falling back to %s",
            question_id,
            code,
            field,
            DEFAULT_LOCALE,
        )
    return str(value[DEFAULT_LOCALE])


def load_category(
    track: str,
    level: str,
    category: str,
    locale: str = DEFAULT_LOCALE,
) -> list[Question]:
    """Load questions for a specific category.

    Args:
        track: Question bank slug (e.g. ``python``, ``database``).
        level: Difficulty level (e.g., "junior", "middle", "senior").
        category: Question category name (e.g., "basics", "oop").
        locale: Locale for question text (default: ``en``).

    Returns:
        List of Question objects. Empty list if file doesn't exist.
    """
    path = QUESTIONS_DIR / track / level / f"{category}.yaml"
    if not path.exists():
        return []

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        return []

    questions = []
    for q in data.get("questions", []):
        qid = q["id"]
        points_raw = q.get("expected_points", [])
        if not isinstance(points_raw, list):
            msg = f"Question {qid}: invalid expected_points"
            raise ValueError(msg)
        questions.append(
            Question(
                id=qid,
                type=q["type"],
                difficulty=q["difficulty"],
                tags=q.get("tags", []),
                text=_resolve_localized_string(
                    q["question"]["text"],
                    locale,
                    field="text",
                    question_id=qid,
                ),
                code=q["question"].get("code"),
                expected_points=tuple(str(point) for point in points_raw),
            )
        )
    return questions


def load_categories(
    track: str,
    level: str,
    categories: list[str],
    locale: str = DEFAULT_LOCALE,
) -> list[Question]:
    """Load and merge questions from multiple categories for one track/level.

    Args:
        track: Question bank slug.
        level: Difficulty level slug.
        categories: Category YAML stems to load.
        locale: Locale for question text.

    Returns:
        De-duplicated list of questions (first occurrence wins by question id).
    """
    seen: set[str] = set()
    merged: list[Question] = []
    for category in categories:
        for question in load_category(track, level, category, locale=locale):
            if question.id in seen:
                continue
            seen.add(question.id)
            merged.append(question)
    return merged


def list_tracks() -> list[str]:
    """List question-bank tracks that have a directory under ``data/questions/``.

    Returns:
        Sorted directory names (e.g. ``python``, ``database``).
    """
    if not QUESTIONS_DIR.exists():
        return []
    return sorted(
        path.name
        for path in QUESTIONS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def list_levels(track: str) -> list[str]:
    """List difficulty levels available for a track.

    Args:
        track: Question bank slug (e.g. ``python``).

    Returns:
        Sorted level directory names (e.g. ``junior``, ``middle``).
    """
    path = QUESTIONS_DIR / track
    if not path.exists():
        return []
    return sorted(
        level.name
        for level in path.iterdir()
        if level.is_dir() and not level.name.startswith(".")
    )


def list_categories(track: str, level: str) -> list[str]:
    """List available categories for a track and level.

    Args:
        track: Question bank slug (e.g. ``python``).
        level: Difficulty level (e.g., "junior", "middle", "senior").

    Returns:
        List of category names (YAML filenames without extension).
        Empty list if directory doesn't exist.
    """
    path = QUESTIONS_DIR / track / level
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.yaml")]
