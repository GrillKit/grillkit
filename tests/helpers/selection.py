# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Helpers for building interview selection JSON in tests."""

from app.interview.domain.serialization import session_to_spec
from app.interview.domain.value_objects import SessionSelection, TrackSelection


def minimal_selection_spec(
    *,
    track: str = "python",
    level: str = "junior",
    categories: tuple[str, ...] | None = None,
    question_count: int = 5,
    task_time_limit_seconds: int | None = None,
) -> str:
    """Build a minimal v2 ``selection_spec`` JSON string for test interviews.

    Args:
        track: Question bank slug.
        level: Difficulty level slug.
        categories: Topic slugs (default: ``("basics",)``).
        question_count: Theory question count stored in the spec.
        task_time_limit_seconds: Optional per-round timer for theory.

    Returns:
        JSON string suitable for ``Interview.selection_spec``.
    """
    return session_to_spec(
        SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track=track,
                    level=level,
                    categories=categories if categories is not None else ("basics",),
                ),
            ),
            question_count=question_count,
            task_time_limit_seconds=task_time_limit_seconds,
        )
    )
