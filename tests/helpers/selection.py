# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Helpers for building interview selection JSON in tests."""

from app.interview.services.rules.selection import (
    InterviewSelection,
    TrackSelection,
    selection_to_spec,
)


def minimal_selection_spec(
    *,
    track: str = "python",
    level: str = "junior",
    categories: list[str] | None = None,
) -> str:
    """Build a minimal ``selection_spec`` JSON string for test interviews.

    Args:
        track: Question bank slug.
        level: Difficulty level slug.
        categories: Topic slugs (default: ``["basics"]``).

    Returns:
        JSON string suitable for ``Interview.selection_spec``.
    """
    return selection_to_spec(
        InterviewSelection(
            sources=[
                TrackSelection(
                    track=track,
                    level=level,
                    categories=categories if categories is not None else ["basics"],
                )
            ]
        )
    )
