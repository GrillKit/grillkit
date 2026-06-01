# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-bank selection and multi-source question planning for interviews."""

from __future__ import annotations

import json
import random
from typing import Any

from app.interview.domain.value_objects import (
    InterviewSelection,
    InterviewSelectionHolder,
    TrackQuestionPools,
    TrackSelection,
)
from app.questions import Question

_TRACK_LABELS: dict[str, str] = {
    "python": "Python",
    "database": "Database / SQL",
    "system-design": "System Design",
}


def track_label(slug: str) -> str:
    """Return a human-readable label for a question-bank track slug.

    Args:
        slug: Track directory name under ``data/questions/``.

    Returns:
        Display label for templates and UI.
    """
    return _TRACK_LABELS.get(slug, slug.replace("-", " ").replace("_", " ").title())


def validate_question_count(selection: InterviewSelection, question_count: int) -> None:
    """Ensure question count allows at least one question per selected topic.

    Args:
        selection: Parsed interview selection.
        question_count: Requested number of questions for the session.

    Raises:
        ValueError: If ``question_count`` is below the number of selected topics.
    """
    topics = selection.topic_count
    if question_count < topics:
        msg = (
            f"Number of questions must be at least {topics} "
            f"(one per selected topic), got {question_count}"
        )
        raise ValueError(msg)


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


def get_interview_selection(interview: InterviewSelectionHolder) -> InterviewSelection:
    """Load selection from an interview row.

    Args:
        interview: Object with ``id`` and ``selection_spec``.

    Returns:
        Parsed interview selection.

    Raises:
        ValueError: If ``selection_spec`` is missing or invalid.
    """
    if not interview.selection_spec:
        raise ValueError(f"Interview {interview.id} has no selection_spec")
    return parse_selection_spec(interview.selection_spec)


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


def selection_sources_summary(selection: InterviewSelection) -> str:
    """Build multi-line sources text for AI evaluation prompts.

    Args:
        selection: Interview selection.

    Returns:
        Bullet list of tracks, levels, and categories.
    """
    lines: list[str] = []
    for source in selection.sources:
        label = track_label(source.track)
        topics = ", ".join(source.categories)
        lines.append(f"- {label} / {source.level}: {topics}")
    return "\n".join(lines)


def interview_display_title(selection: InterviewSelection) -> str:
    """Build page title from selection.

    Args:
        selection: Interview selection.

    Returns:
        Title such as ``Python Interview`` or ``Multi-topic Interview``.
    """
    if selection.is_multi():
        return "Multi-topic Interview"
    source = selection.sources[0]
    return f"{track_label(source.track)} Interview"


def parse_selection_json(raw_json: str) -> InterviewSelection:
    """Parse setup form ``selection_json`` field.

    Args:
        raw_json: JSON string from POST body.

    Returns:
        Validated InterviewSelection.

    Raises:
        ValueError: If JSON is invalid or selection fails validation.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid selection JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid selection JSON: expected object")
    return selection_from_payload(data)


def _allocate_proportional(sizes: list[int], total: int) -> list[int]:
    """Distribute ``total`` across buckets proportionally to ``sizes``.

    Args:
        sizes: Weight per bucket (typically pool sizes).
        total: Number of slots to allocate.

    Returns:
        Per-bucket counts summing to ``total`` (may be zeros for empty sizes).
    """
    if total <= 0:
        return [0] * len(sizes)
    weight_sum = sum(sizes)
    if weight_sum == 0:
        return [0] * len(sizes)

    raw = [total * size / weight_sum for size in sizes]
    counts = [int(value) for value in raw]
    remainder = total - sum(counts)
    fractions = [(raw[i] - counts[i], i) for i in range(len(sizes))]
    fractions.sort(reverse=True)
    for _, index in fractions[:remainder]:
        counts[index] += 1
    return counts


def plan_questions(
    selection: InterviewSelection,
    question_count: int,
    track_pools: list[TrackQuestionPools],
) -> list[Question]:
    """Build ordered question list from pre-loaded pools.

    Picks one random question per selected topic, then fills remaining slots
    proportionally by track pool size. Questions are grouped by track
    (form order) with random order within each block.

    Args:
        selection: Validated interview selection.
        question_count: Target number of questions (>= topic count).
        track_pools: Loaded pools in the same order as ``selection.sources``.

    Returns:
        Ordered list of Question instances.

    Raises:
        ValueError: If pools are empty or misaligned with the selection.
    """
    if len(track_pools) != len(selection.sources):
        raise ValueError("track_pools must match selection.sources")

    picked: list[Question] = []
    picked_ids: set[str] = set()
    question_track: dict[str, str] = {}
    pools_by_source: list[tuple[TrackSelection, tuple[Question, ...]]] = []

    for pools in track_pools:
        source = pools.source
        full_pool = pools.full_pool
        if not full_pool:
            raise ValueError(f"No questions found for {source.track}/{source.level}")
        pools_by_source.append((source, full_pool))

        for category in source.categories:
            category_pool = pools.category_pools.get(category, ())
            if not category_pool:
                raise ValueError(
                    f"No questions found for {source.track}/{source.level}/{category}"
                )
            available = [q for q in category_pool if q.id not in picked_ids]
            if not available:
                available = list(category_pool)
            question = random.choice(available)
            picked.append(question)
            picked_ids.add(question.id)
            question_track[question.id] = source.track

    extra = question_count - len(picked)
    if extra > 0:
        remaining_by_track: list[tuple[str, list[Question]]] = []
        for source, full_pool in pools_by_source:
            remaining_pool = [q for q in full_pool if q.id not in picked_ids]
            if remaining_pool:
                remaining_by_track.append((source.track, remaining_pool))

        max_extra = sum(len(pool) for _, pool in remaining_by_track)
        to_allocate = min(extra, max_extra)
        if to_allocate > 0 and remaining_by_track:
            sizes = [len(pool) for _, pool in remaining_by_track]
            counts = _allocate_proportional(sizes, to_allocate)
            for (track_slug, pool), count in zip(
                remaining_by_track, counts, strict=True
            ):
                if count <= 0:
                    continue
                sampled = random.sample(pool, min(count, len(pool)))
                picked.extend(sampled)
                for question in sampled:
                    picked_ids.add(question.id)
                    question_track[question.id] = track_slug

    by_track: dict[str, list[Question]] = {}
    for question in picked:
        track_key = question_track[question.id]
        by_track.setdefault(track_key, []).append(question)

    ordered: list[Question] = []
    for source in selection.sources:
        block = by_track.get(source.track, [])
        random.shuffle(block)
        ordered.extend(block)

    return ordered[:question_count]
