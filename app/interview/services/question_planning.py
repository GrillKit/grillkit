# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Load question banks and build interview question plans."""

from app.interview.domain.value_objects import InterviewSelection, TrackQuestionPools
from app.interview.services.rules.selection import plan_questions, track_label
from app.questions import (
    Question,
    list_categories,
    list_levels,
    list_tracks,
    load_categories,
    load_category,
)
from app.shared.locales import normalize_locale


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
    """Load YAML question pools for each track source in a selection.

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
        full_pool = load_categories(
            source.track, source.level, list(source.categories), locale=locale
        )
        category_pools: dict[str, list[Question]] = {}
        for category in source.categories:
            category_pool = load_category(
                source.track, source.level, category, locale=locale
            )
            category_pools[category] = category_pool
        pools.append(
            TrackQuestionPools(
                source=source,
                full_pool=tuple(full_pool),
                category_pools={
                    category: tuple(pool) for category, pool in category_pools.items()
                },
            )
        )
    return pools


def build_question_plan(
    selection: InterviewSelection,
    question_count: int,
    locale: str = "en",
) -> list[Question]:
    """Build ordered question list for a multi-source interview.

    Args:
        selection: Validated interview selection.
        question_count: Target number of questions (>= topic count).
        locale: Locale for question text.

    Returns:
        Ordered list of Question instances.

    Raises:
        ValueError: If validation fails or pools are empty.
    """
    validate_selection(selection)
    track_pools = load_track_pools(selection, locale)
    return plan_questions(selection, question_count, track_pools)
