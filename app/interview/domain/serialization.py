# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persistence serialization for interview domain value objects."""

from __future__ import annotations

import json
from typing import Any

from app.interview.domain.value_objects import (
    InterviewSelection,
    TrackSelection,
)


def selection_to_spec(selection: InterviewSelection) -> str:
    """Serialize selection to JSON for ``Interview.selection_spec``.

    Args:
        selection: Interview selection.

    Returns:
        JSON string with a ``sources`` list.
    """
    payload = {
        "sources": [
            {
                "track": source.track,
                "level": source.level,
                "categories": list(source.categories),
            }
            for source in selection.sources
        ],
    }
    return json.dumps(payload, separators=(",", ":"))


def selection_from_payload(data: dict[str, Any]) -> InterviewSelection:
    """Build ``InterviewSelection`` from a JSON-compatible dict.

    Args:
        data: Dict with ``sources`` list.

    Returns:
        InterviewSelection instance.

    Raises:
        ValueError: If payload shape is invalid.
    """
    sources_raw = data.get("sources")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ValueError("Invalid selection_spec: missing sources")

    sources: list[TrackSelection] = []
    for item in sources_raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid selection_spec: source must be an object")
        track = item.get("track")
        level = item.get("level")
        categories = item.get("categories")
        if not isinstance(track, str) or not isinstance(level, str):
            raise ValueError("Invalid selection_spec: track and level required")
        if not isinstance(categories, list) or not categories:
            raise ValueError("Invalid selection_spec: categories required")
        sources.append(
            TrackSelection(
                track=track,
                level=level,
                categories=tuple(str(c) for c in categories),
            )
        )
    return InterviewSelection(sources=tuple(sources))


def parse_selection_spec(raw: str) -> InterviewSelection:
    """Parse ``selection_spec`` JSON from the database.

    Args:
        raw: JSON string stored on ``Interview.selection_spec``.

    Returns:
        Parsed selection.

    Raises:
        ValueError: If ``raw`` is empty or invalid.
    """
    if not raw:
        raise ValueError("selection_spec is empty")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("selection_spec must be a JSON object")
    return selection_from_payload(data)


def parse_overall_feedback(raw: str | None) -> dict[str, Any] | None:
    """Parse ``overall_feedback`` JSON from the database.

    Args:
        raw: JSON string stored on the interview row.

    Returns:
        Parsed dict, or None if the session has no feedback.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"overall_feedback": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"overall_feedback": raw}
