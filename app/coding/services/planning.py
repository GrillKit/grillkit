# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Load coding task banks and build coding section task plans."""

from app.coding.domain.task_spec import task_spec_from_bank_task
from app.coding.domain.value_objects import PlannedCodingTask
from app.interview.domain.value_objects import (
    InterviewSelection,
    PlannedQuestion,
    TrackQuestionPools,
)
from app.shared.coding import (
    CodingTask,
    list_categories,
    list_levels,
    list_tracks,
    load_categories,
    load_category,
)
from app.shared.locales import normalize_locale


def _to_planned_question(task: CodingTask) -> PlannedQuestion:
    """Map a coding bank row to a generic planned question for selection.

    Args:
        task: Loaded coding task.

    Returns:
        Planned question used by shared selection planning.
    """
    return PlannedQuestion(id=task.id, text=task.text, code=None)


def validate_selection(selection: InterviewSelection) -> None:
    """Validate selection against the on-disk coding task bank.

    Args:
        selection: Parsed coding branch selection.

    Raises:
        ValueError: If selection is empty or references unknown bank paths.
    """
    from app.interview.services.rules.selection import track_label

    if not selection.sources:
        raise ValueError("Select at least one coding track and topic")

    tracks = set(list_tracks())
    for source in selection.sources:
        if source.track not in tracks:
            raise ValueError(f"Unknown coding track: {source.track}")
        levels = set(list_levels(source.track))
        if source.level not in levels:
            raise ValueError(
                f"Unknown level '{source.level}' for coding track '{source.track}'"
            )
        if not source.categories:
            raise ValueError(
                f"Select at least one coding topic for {track_label(source.track)}"
            )
        available = set(list_categories(source.track, source.level))
        for category in source.categories:
            if category not in available:
                raise ValueError(
                    f"Unknown coding topic '{category}' for "
                    f"{source.track}/{source.level}"
                )


def validate_task_count(selection: InterviewSelection, task_count: int) -> None:
    """Ensure task count allows at least one task per selected topic.

    Args:
        selection: Parsed coding branch selection.
        task_count: Requested number of coding tasks.

    Raises:
        ValueError: If ``task_count`` is below the number of selected topics.
    """
    topics = selection.topic_count
    if task_count < topics:
        msg = (
            f"Number of coding tasks must be at least {topics} "
            f"(one per selected topic), got {task_count}"
        )
        raise ValueError(msg)


def load_track_pools(
    selection: InterviewSelection,
    locale: str,
) -> list[TrackQuestionPools]:
    """Load YAML coding task pools for each track source in a selection.

    Args:
        selection: Validated coding selection.
        locale: Locale for task prompt text.

    Returns:
        Loaded pools in the same order as ``selection.sources``.

    Raises:
        ValueError: If a pool is empty or a category has no tasks.
    """
    locale = normalize_locale(locale)
    pools: list[TrackQuestionPools] = []
    for source in selection.sources:
        full_pool = load_categories(
            source.track, source.level, list(source.categories), locale=locale
        )
        category_pools: dict[str, list[CodingTask]] = {}
        for category in source.categories:
            category_pool = load_category(
                source.track, source.level, category, locale=locale
            )
            category_pools[category] = category_pool
        pools.append(
            TrackQuestionPools(
                source=source,
                full_pool=tuple(_to_planned_question(task) for task in full_pool),
                category_pools={
                    category: tuple(_to_planned_question(task) for task in pool)
                    for category, pool in category_pools.items()
                },
            )
        )
    return pools


def _task_by_id(
    selection: InterviewSelection,
    locale: str,
) -> dict[str, CodingTask]:
    """Load all coding tasks for a selection keyed by task id.

    Args:
        selection: Validated coding selection.
        locale: Locale for task prompt text.

    Returns:
        Mapping from task id to loaded coding task row.
    """
    locale = normalize_locale(locale)
    tasks: dict[str, CodingTask] = {}
    for source in selection.sources:
        for category in source.categories:
            for task in load_category(
                source.track, source.level, category, locale=locale
            ):
                tasks.setdefault(task.id, task)
    return tasks


def build_coding_task_plan(
    selection: InterviewSelection,
    task_count: int,
    locale: str = "en",
) -> tuple[PlannedCodingTask, ...]:
    """Build ordered coding task list for a multi-source section.

    Args:
        selection: Validated coding selection.
        task_count: Target number of tasks (>= topic count).
        locale: Locale for task prompt text.

    Returns:
        Ordered planned coding tasks.

    Raises:
        ValueError: If validation fails or pools are empty.
    """
    from app.interview.services.rules.selection import plan_questions

    validate_selection(selection)
    validate_task_count(selection, task_count)
    track_pools = load_track_pools(selection, locale)
    planned = plan_questions(selection, task_count, track_pools)
    tasks_by_id = _task_by_id(selection, locale)
    result: list[PlannedCodingTask] = []
    for question in planned:
        task = tasks_by_id.get(question.id)
        if task is None:
            raise ValueError(f"Coding task {question.id} not found in bank")
        result.append(
            PlannedCodingTask(
                id=task.id,
                text=task.text,
                task_spec=task_spec_from_bank_task(task),
            )
        )
    return tuple(result)
