# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""YAML question loader.

This module provides functionality for loading interview questions
from YAML files organized by language, level, and category.
"""

import logging
from dataclasses import dataclass
from typing import Any

import yaml

from app.paths import QUESTIONS_DIR
from app.shared.domain.locales import DEFAULT_LOCALE, normalize_locale

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


def _resolve_follow_ups(value: Any, locale: str, question_id: str) -> list[str]:
    """Return follow-up strings for a locale.

    Args:
        value: Legacy list (English) or ``{locale: [str, ...]}`` map.
        locale: Requested locale code.
        question_id: Question id for warning logs.

    Returns:
        List of follow-up question strings.

    Raises:
        ValueError: If value shape is invalid.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, dict):
        msg = f"Question {question_id}: invalid follow_ups (expected list or locale map)"
        raise ValueError(msg)
    code = normalize_locale(locale)
    if code in value:
        return [str(item) for item in value[code]]
    if DEFAULT_LOCALE in value:
        if code != DEFAULT_LOCALE:
            logger.warning(
                "Question %s: no %s follow_ups, falling back to %s",
                question_id,
                code,
                DEFAULT_LOCALE,
            )
        return [str(item) for item in value[DEFAULT_LOCALE]]
    msg = f"Question {question_id}: missing required '{DEFAULT_LOCALE}' in follow_ups"
    raise ValueError(msg)


def load_category(
    language: str,
    level: str,
    category: str,
    locale: str = DEFAULT_LOCALE,
) -> list[Question]:
    """Load questions for a specific category.

    Args:
        language: Programming language (e.g., "python", "javascript").
        level: Difficulty level (e.g., "junior", "middle", "senior").
        category: Question category name (e.g., "basics", "oop").
        locale: Locale for question text and bank follow-ups (default: ``en``).

    Returns:
        List of Question objects. Empty list if file doesn't exist.
    """
    path = QUESTIONS_DIR / language / level / f"{category}.yaml"
    if not path.exists():
        return []

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        return []

    questions = []
    for q in data.get("questions", []):
        qid = q["id"]
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
                follow_ups=_resolve_follow_ups(q.get("follow_ups"), locale, qid),
                expected_points=q.get("expected_points", []),
            )
        )
    return questions


def list_languages() -> list[str]:
    """List programming languages that have a question bank directory.

    Returns:
        Sorted directory names under ``data/questions/`` (e.g. ``python``).
    """
    if not QUESTIONS_DIR.exists():
        return []
    return sorted(
        path.name
        for path in QUESTIONS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def list_levels(language: str) -> list[str]:
    """List difficulty levels available for a programming language.

    Args:
        language: Programming language slug (e.g. ``python``).

    Returns:
        Sorted level directory names (e.g. ``junior``, ``middle``).
    """
    path = QUESTIONS_DIR / language
    if not path.exists():
        return []
    return sorted(
        level.name
        for level in path.iterdir()
        if level.is_dir() and not level.name.startswith(".")
    )


def list_categories(language: str, level: str) -> list[str]:
    """List available categories for a language and level.

    Args:
        language: Programming language (e.g., "python", "javascript").
        level: Difficulty level (e.g., "junior", "middle", "senior").

    Returns:
        List of category names (YAML filenames without extension).
        Empty list if directory doesn't exist.
    """
    path = QUESTIONS_DIR / language / level
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.yaml")]
