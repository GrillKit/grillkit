# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""YAML coding task loader.

This module loads coding interview tasks from YAML files organized by
track, level, and category under ``data/coding/``.
"""

from dataclasses import dataclass
from typing import Any

import yaml

from app.shared.locales import DEFAULT_LOCALE
from app.shared.paths import CODING_DIR
from app.shared.questions import _resolve_localized_string

EvaluationMode = str
CodingLanguage = str


@dataclass(frozen=True, slots=True)
class CodingTestCase:
    """Single stdin/stdout test case for Judge0 execution.

    Attributes:
        name: Human-readable test identifier.
        stdin: Input passed to the program.
        expected_stdout: Expected standard output.
    """

    name: str
    stdin: str
    expected_stdout: str


@dataclass(frozen=True, slots=True)
class CodingSpec:
    """Execution and evaluation metadata for a coding task.

    Attributes:
        language: Programming language slug (e.g. ``python``).
        evaluation_mode: ``tests`` for algorithmic tasks or ``ai`` for open-ended.
        starter_code: Initial editor contents shown to the candidate.
        entrypoint: Callable name for the test harness (``tests`` mode).
        public_tests: Visible test cases executed on Run.
        hidden_tests: Hidden test cases executed on Submit.
        time_limit_seconds: Per-submission CPU time limit.
        memory_limit_kb: Per-submission memory limit.
    """

    language: CodingLanguage
    evaluation_mode: EvaluationMode
    starter_code: str | None = None
    entrypoint: str | None = None
    public_tests: tuple[CodingTestCase, ...] = ()
    hidden_tests: tuple[CodingTestCase, ...] = ()
    time_limit_seconds: int | None = None
    memory_limit_kb: int | None = None


@dataclass(frozen=True, slots=True)
class CodingTask:
    """Coding challenge loaded from the task bank.

    Attributes:
        id: Unique task identifier.
        difficulty: Difficulty level (1-5 scale).
        tags: List of topic tags.
        text: Coding assignment text shown to the candidate.
        coding: Execution and evaluation specification.
        expected_points: Rubric bullets for AI evaluation.
    """

    id: str
    difficulty: int
    tags: tuple[str, ...]
    text: str
    coding: CodingSpec
    expected_points: tuple[str, ...] = ()


def _parse_test_cases(
    raw_cases: Any, *, task_id: str, field: str
) -> tuple[CodingTestCase, ...]:
    """Parse a list of YAML test case dicts.

    Args:
        raw_cases: YAML list value.
        task_id: Task id for error messages.
        field: Field name for error messages.

    Returns:
        Parsed test cases.

    Raises:
        ValueError: If the shape is invalid.
    """
    if raw_cases is None:
        return ()
    if not isinstance(raw_cases, list):
        msg = f"Coding task {task_id}: invalid {field} (expected list)"
        raise ValueError(msg)
    cases: list[CodingTestCase] = []
    for index, item in enumerate(raw_cases):
        if not isinstance(item, dict):
            msg = f"Coding task {task_id}: invalid {field}[{index}]"
            raise ValueError(msg)
        name = item.get("name")
        if not isinstance(name, str) or not name:
            msg = f"Coding task {task_id}: {field}[{index}] missing name"
            raise ValueError(msg)
        stdin = item.get("stdin", "")
        expected_stdout = item.get("expected_stdout", "")
        if not isinstance(stdin, str) or not isinstance(expected_stdout, str):
            msg = (
                f"Coding task {task_id}: {field}[{index}] invalid stdin/expected_stdout"
            )
            raise ValueError(msg)
        cases.append(
            CodingTestCase(
                name=name,
                stdin=stdin,
                expected_stdout=expected_stdout,
            )
        )
    return tuple(cases)


def _parse_coding_spec(raw: dict[str, Any], *, task_id: str) -> CodingSpec:
    """Parse the ``coding`` block from a YAML task row.

    Args:
        raw: Task dict from YAML.
        task_id: Task id for error messages.

    Returns:
        Parsed coding specification.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    coding = raw.get("coding")
    if not isinstance(coding, dict):
        msg = f"Coding task {task_id}: missing coding block"
        raise ValueError(msg)
    language = coding.get("language")
    evaluation_mode = coding.get("evaluation_mode")
    if not isinstance(language, str) or not language:
        msg = f"Coding task {task_id}: missing coding.language"
        raise ValueError(msg)
    if evaluation_mode not in {"tests", "ai"}:
        msg = f"Coding task {task_id}: invalid coding.evaluation_mode"
        raise ValueError(msg)
    starter_code = coding.get("starter_code")
    if starter_code is not None and not isinstance(starter_code, str):
        msg = f"Coding task {task_id}: invalid coding.starter_code"
        raise ValueError(msg)
    entrypoint = coding.get("entrypoint")
    if entrypoint is not None and not isinstance(entrypoint, str):
        msg = f"Coding task {task_id}: invalid coding.entrypoint"
        raise ValueError(msg)
    time_limit = coding.get("time_limit_seconds")
    if time_limit is not None and not isinstance(time_limit, int):
        msg = f"Coding task {task_id}: invalid coding.time_limit_seconds"
        raise ValueError(msg)
    memory_limit = coding.get("memory_limit_kb")
    if memory_limit is not None and not isinstance(memory_limit, int):
        msg = f"Coding task {task_id}: invalid coding.memory_limit_kb"
        raise ValueError(msg)
    return CodingSpec(
        language=language,
        evaluation_mode=evaluation_mode,
        starter_code=starter_code,
        entrypoint=entrypoint,
        public_tests=_parse_test_cases(
            coding.get("public_tests"), task_id=task_id, field="coding.public_tests"
        ),
        hidden_tests=_parse_test_cases(
            coding.get("hidden_tests"), task_id=task_id, field="coding.hidden_tests"
        ),
        time_limit_seconds=time_limit,
        memory_limit_kb=memory_limit,
    )


def _parse_task(raw: dict[str, Any], *, locale: str) -> CodingTask:
    """Parse one YAML task row.

    Args:
        raw: Task dict from YAML.
        locale: Locale for prompt text.

    Returns:
        Parsed coding task.

    Raises:
        ValueError: If required fields are missing or invalid.
    """
    task_id = raw.get("id")
    if not isinstance(task_id, str) or not task_id:
        msg = "Coding task row missing id"
        raise ValueError(msg)
    difficulty = raw.get("difficulty")
    if not isinstance(difficulty, int):
        msg = f"Coding task {task_id}: missing difficulty"
        raise ValueError(msg)
    coding = raw.get("coding")
    if not isinstance(coding, dict):
        msg = f"Coding task {task_id}: missing coding block"
        raise ValueError(msg)
    assignment = coding.get("assignment")
    if assignment is None:
        msg = f"Coding task {task_id}: missing coding.assignment"
        raise ValueError(msg)
    tags_raw = raw.get("tags", [])
    if not isinstance(tags_raw, list):
        msg = f"Coding task {task_id}: invalid tags"
        raise ValueError(msg)
    points_raw = raw.get("expected_points", [])
    if not isinstance(points_raw, list):
        msg = f"Coding task {task_id}: invalid expected_points"
        raise ValueError(msg)
    return CodingTask(
        id=task_id,
        difficulty=difficulty,
        tags=tuple(str(tag) for tag in tags_raw),
        text=_resolve_localized_string(
            assignment,
            locale,
            field="assignment",
            question_id=task_id,
        ),
        coding=_parse_coding_spec(raw, task_id=task_id),
        expected_points=tuple(str(point) for point in points_raw),
    )


def load_category(
    track: str,
    level: str,
    category: str,
    locale: str = DEFAULT_LOCALE,
) -> list[CodingTask]:
    """Load coding tasks for a specific category.

    Args:
        track: Task bank slug (e.g. ``python``).
        level: Difficulty level (e.g. ``junior``).
        category: Category YAML stem (e.g. ``basics``).
        locale: Locale for task prompt text.

    Returns:
        List of coding tasks. Empty list if the file does not exist.
    """
    path = CODING_DIR / track / level / f"{category}.yaml"
    if not path.exists():
        return []

    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        return []

    tasks: list[CodingTask] = []
    for raw in data.get("tasks", []):
        if not isinstance(raw, dict):
            continue
        tasks.append(_parse_task(raw, locale=locale))
    return tasks


def load_categories(
    track: str,
    level: str,
    categories: list[str],
    locale: str = DEFAULT_LOCALE,
) -> list[CodingTask]:
    """Load and merge coding tasks from multiple categories.

    Args:
        track: Task bank slug.
        level: Difficulty level slug.
        categories: Category YAML stems to load.
        locale: Locale for task prompt text.

    Returns:
        De-duplicated list of tasks (first occurrence wins by task id).
    """
    seen: set[str] = set()
    merged: list[CodingTask] = []
    for category in categories:
        for task in load_category(track, level, category, locale=locale):
            if task.id in seen:
                continue
            seen.add(task.id)
            merged.append(task)
    return merged


def list_tracks() -> list[str]:
    """List task-bank tracks under ``data/coding/``.

    Returns:
        Sorted directory names (e.g. ``python``).
    """
    if not CODING_DIR.exists():
        return []
    return sorted(
        path.name
        for path in CODING_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def list_levels(track: str) -> list[str]:
    """List difficulty levels available for a coding track.

    Args:
        track: Task bank slug.

    Returns:
        Sorted level directory names.
    """
    path = CODING_DIR / track
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
        track: Task bank slug.
        level: Difficulty level slug.

    Returns:
        Category YAML stems. Empty list if the directory does not exist.
    """
    path = CODING_DIR / track / level
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.yaml")]
