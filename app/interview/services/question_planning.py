# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Load question banks and build interview question plans."""

from app.interview.domain.selection import (
    InterviewSelection,
    LanguageQuestionPools,
    language_label,
    plan_questions,
)
from app.questions import (
    Question,
    list_categories,
    list_languages,
    list_levels,
    load_categories,
    load_category,
)
from app.shared.domain.locales import normalize_locale


def validate_selection(selection: InterviewSelection) -> None:
    """Validate selection against the on-disk question bank.

    Args:
        selection: Parsed interview selection.

    Raises:
        ValueError: If selection is empty or references unknown bank paths.
    """
    if not selection.sources:
        raise ValueError("Select at least one language and topic")

    languages = set(list_languages())
    for source in selection.sources:
        if source.language not in languages:
            raise ValueError(f"Unknown language: {source.language}")
        levels = set(list_levels(source.language))
        if source.level not in levels:
            raise ValueError(
                f"Unknown level '{source.level}' for language '{source.language}'"
            )
        if not source.categories:
            raise ValueError(
                f"Select at least one topic for {language_label(source.language)}"
            )
        available = set(list_categories(source.language, source.level))
        for category in source.categories:
            if category not in available:
                raise ValueError(
                    f"Unknown topic '{category}' for {source.language}/{source.level}"
                )


def load_language_pools(
    selection: InterviewSelection,
    locale: str,
) -> list[LanguageQuestionPools]:
    """Load YAML question pools for each language source in a selection.

    Args:
        selection: Validated interview selection.
        locale: Locale for question text.

    Returns:
        Loaded pools in the same order as ``selection.sources``.

    Raises:
        ValueError: If a pool is empty or a category has no questions.
    """
    locale = normalize_locale(locale)
    pools: list[LanguageQuestionPools] = []
    for source in selection.sources:
        full_pool = load_categories(
            source.language, source.level, source.categories, locale=locale
        )
        category_pools: dict[str, list[Question]] = {}
        for category in source.categories:
            category_pool = load_category(
                source.language, source.level, category, locale=locale
            )
            category_pools[category] = category_pool
        pools.append(
            LanguageQuestionPools(
                source=source,
                full_pool=full_pool,
                category_pools=category_pools,
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
    language_pools = load_language_pools(selection, locale)
    return plan_questions(selection, question_count, language_pools)
