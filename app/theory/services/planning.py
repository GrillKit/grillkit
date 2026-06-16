# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Load question banks and build theory section question plans."""

from app.interview.domain.value_objects import (
    InterviewSelection,
    PlannedQuestion,
    TrackQuestionPools,
)
from app.interview.services.rules.bank_selection import (
    BankCatalog,
    BankSelectionMessages,
    track_label,
    validate_bank_selection,
)
from app.interview.services.rules.selection import plan_questions
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

_THEORY_BANK_CATALOG = BankCatalog(
    list_tracks=list_tracks,
    list_levels=list_levels,
    list_categories=list_categories,
)
_THEORY_BANK_MESSAGES = BankSelectionMessages(
    empty_sources="Select at least one track and topic",
    unknown_track=lambda track: f"Unknown track: {track}",
    unknown_level=lambda level, track: f"Unknown level '{level}' for track '{track}'",
    empty_categories=lambda track: (
        f"Select at least one topic for {track_label(track)}"
    ),
    unknown_category=lambda category, track, level: (
        f"Unknown topic '{category}' for {track}/{level}"
    ),
)


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
    validate_bank_selection(
        selection,
        _THEORY_BANK_CATALOG,
        _THEORY_BANK_MESSAGES,
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
    *,
    excluded_ids: frozenset[str] = frozenset(),
) -> tuple[PlannedTheoryQuestion, ...]:
    """Build ordered theory question list for a multi-source section.

    Args:
        selection: Validated interview selection.
        question_count: Target number of questions (>= topic count).
        locale: Locale for question text.
        excluded_ids: Question IDs to remove from pools before planning.

    Returns:
        Ordered planned theory questions.

    Raises:
        ValueError: If validation fails or pools are empty.
    """
    validate_selection(selection)
    track_pools = load_track_pools(selection, locale)
    planned = plan_questions(
        selection,
        question_count,
        track_pools,
        excluded_ids=excluded_ids,
    )
    return tuple(
        PlannedTheoryQuestion(
            id=question.id,
            text=question.text,
            code=question.code,
            expected_points=question.expected_points,
        )
        for question in planned
    )
