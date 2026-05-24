# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Helpers for building interview selection JSON in tests."""

from app.interview.domain.selection import (
    InterviewSelection,
    LanguageSelection,
    selection_to_spec,
)


def minimal_selection_spec(
    *,
    language: str = "python",
    level: str = "junior",
    categories: list[str] | None = None,
) -> str:
    """Build a minimal ``selection_spec`` JSON string for test interviews.

    Args:
        language: Question bank slug.
        level: Difficulty level slug.
        categories: Topic slugs (default: ``["basics"]``).

    Returns:
        JSON string suitable for ``Interview.selection_spec``.
    """
    return selection_to_spec(
        InterviewSelection(
            sources=[
                LanguageSelection(
                    language=language,
                    level=level,
                    categories=categories if categories is not None else ["basics"],
                )
            ]
        )
    )
