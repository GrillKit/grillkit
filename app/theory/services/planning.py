# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Load question banks and build theory section question plans."""

from app.interview.domain.value_objects import (
    InterviewSelection,
    PlannedQuestion,
    TrackQuestionPools,
)
from app.interview.services.rules.selection import plan_questions, track_label
from app.shared.locales import normalize_locale
from app.shared.questions import (
    Question,
    list_categories,
    list_levels,
    list_tracks,
    load_categories,
    load_category,
)
from app.theory.domain.value_objects import PlannedTheoryQuestion


def _theory_questions_only(questions: list[Question]) -> list[Question]:
    """Drop coding-bank rows that may still appear in legacy theory YAML files.

    Args:
        questions: Loaded question rows from the theory bank.

    Returns:
        Questions eligible for theory section planning.
    """
    return [question for question in questions if question.type != "coding"]


def _to_planned(question: Question) -> PlannedQuestion:
    """Map a YAML question bank row to a domain planned question.

    Args:
        question: Loaded question from ``app.shared.questions``.

    Returns:
        Domain value object for theory section creation.
    """
    return PlannedQuestion(
        id=question.id,
        text=question.text,
        code=question.code,
        expected_points=question.expected_points,
    )


def validate_selection(selection: InterviewSelection) -> None:
    """Validate selection against the on-disk question bank.

    Args:
        selection: Parsed interview selection.

    Raises:
        ValueError: If selection is empty or references unknown bank paths.
    """
    if not selection.sources:
        raise ValueError("Select at least one track and topic")

    tracks = set(list_tracks())
    for source in selection.sources:
        if source.track not in tracks:
            raise ValueError(f"Unknown track: {source.track}")
        levels = set(list_levels(source.track))
        if source.level not in levels:
            raise ValueError(
                f"Unknown level '{source.level}' for track '{source.track}'"
            )
        if not source.categories:
            raise ValueError(
                f"Select at least one topic for {track_label(source.track)}"
            )
        available = set(list_categories(source.track, source.level))
        for category in source.categories:
            if category not in available:
                raise ValueError(
                    f"Unknown topic '{category}' for {source.track}/{source.level}"
                )


def load_track_pools(
    selection: InterviewSelection,
    locale: str,
) -> list[TrackQuestionPools]:
    """Load YAML theory question pools for each track source in a selection.

    Args:
        selection: Validated interview selection.
        locale: Locale for question text.

    Returns:
        Loaded pools in the same order as ``selection.sources``.

    Raises:
        ValueError: If a pool is empty or a category has no questions.
    """
    locale = normalize_locale(locale)
    pools: list[TrackQuestionPools] = []
    for source in selection.sources:
        full_pool = _theory_questions_only(
            load_categories(
                source.track, source.level, list(source.categories), locale=locale
            )
        )
        category_pools: dict[str, list[Question]] = {}
        for category in source.categories:
            category_pool = _theory_questions_only(
                load_category(source.track, source.level, category, locale=locale)
            )
            category_pools[category] = category_pool
        pools.append(
            TrackQuestionPools(
                source=source,
                full_pool=tuple(_to_planned(q) for q in full_pool),
                category_pools={
                    category: tuple(_to_planned(q) for q in pool)
                    for category, pool in category_pools.items()
                },
            )
        )
    return pools


def build_theory_question_plan(
    selection: InterviewSelection,
    question_count: int,
    locale: str = "en",
) -> tuple[PlannedTheoryQuestion, ...]:
    """Build ordered theory question list for a multi-source section.

    Args:
        selection: Validated interview selection.
        question_count: Target number of questions (>= topic count).
        locale: Locale for question text.

    Returns:
        Ordered planned theory questions.

    Raises:
        ValueError: If validation fails or pools are empty.
    """
    validate_selection(selection)
    track_pools = load_track_pools(selection, locale)
    planned = plan_questions(selection, question_count, track_pools)
    return tuple(
        PlannedTheoryQuestion(
            id=question.id,
            text=question.text,
            code=question.code,
            expected_points=question.expected_points,
        )
        for question in planned
    )
