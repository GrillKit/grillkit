# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-bank selection and multi-source question planning for interviews."""

from __future__ import annotations

import json
import random

from app.coding.services.availability import is_coding_available
from app.coding.services.planning import validate_selection as validate_coding_selection
from app.coding.services.planning import validate_task_count
from app.interview.domain.serialization import (
    parse_session_spec,
    session_from_payload,
)
from app.interview.domain.value_objects import (
    SESSION_MODE_LABELS,
    InterviewSelection,
    InterviewSelectionHolder,
    PlannedQuestion,
    SessionSelection,
    TrackQuestionPools,
    TrackSelection,
)
from app.interview.services.rules.bank_selection import track_label


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
    return parse_session_spec(interview.selection_spec).theory_selection


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


def selection_summary_lines(selection: InterviewSelection) -> list[str]:
    """Build display lines for each track source in a selection.

    Args:
        selection: Interview selection.

    Returns:
        Lines such as ``Python / middle: basics, oop``.
    """
    lines: list[str] = []
    for source in selection.sources:
        label = track_label(source.track)
        topics = ", ".join(
            cat.replace("-", " ").replace("_", " ").title() for cat in source.categories
        )
        lines.append(f"{label} / {source.level}: {topics}")
    return lines


def interview_display_title(selection: InterviewSelection) -> str:
    """Build page title from selection.

    Args:
        selection: Interview selection.

    Returns:
        Title such as ``Python Interview`` or ``Multi-topic Interview``.
    """
    if not selection.sources:
        return "Interview"
    if selection.is_multi():
        return "Multi-topic Interview"
    source = selection.sources[0]
    return f"{track_label(source.track)} Interview"


def session_display_title(session: SessionSelection) -> str:
    """Build page title from a full session selection.

    Args:
        session: Session selection including mode and branches.

    Returns:
        Title based on the active branch sources, or a mode fallback.
    """
    if session.session_mode == "coding_only":
        selection = session.coding_selection
    else:
        selection = session.theory_selection

    if selection.sources:
        return interview_display_title(selection)

    mode_label = SESSION_MODE_LABELS.get(session.session_mode, "Interview")
    return f"{mode_label} Interview"


def session_selection_summary_lines(session: SessionSelection) -> list[str]:
    """Build display lines for the active session branches.

    Args:
        session: Session selection including mode and branches.

    Returns:
        Summary lines for theory and/or coding sources.
    """
    if session.session_mode == "coding_only":
        return selection_summary_lines(session.coding_selection)

    lines = selection_summary_lines(session.theory_selection)
    if session.session_mode in ("theory_then_coding", "coding_then_theory"):
        lines.extend(selection_summary_lines(session.coding_selection))
    return lines


def validate_session_selection(session: SessionSelection) -> None:
    """Validate a parsed session selection from setup.

    Args:
        session: Session selection including mode and branch specs.

    Raises:
        ValueError: If branches are inconsistent or banks reject the selection.
    """
    if not session.theory.enabled and not session.coding.enabled:
        raise ValueError("At least one section must be enabled")
    if session.theory.enabled:
        if not session.theory.sources:
            raise ValueError("Select at least one theory track and topic")
        validate_question_count(session.theory_selection, session.theory.question_count)
    if session.coding.enabled:
        if not is_coding_available():
            raise ValueError(
                "Coding is not available. Enable CODING_ENABLED and ensure "
                "Judge0 is running, or choose a theory-only session."
            )
        if not session.coding.sources:
            raise ValueError("Select at least one coding track and topic")
        validate_coding_selection(session.coding_selection)
        validate_task_count(session.coding_selection, session.coding.question_count)


def parse_session_json(raw_json: str) -> SessionSelection:
    """Parse setup form ``selection_json`` field (v2 session selection).

    Args:
        raw_json: JSON string from POST body.

    Returns:
        Validated session selection.

    Raises:
        ValueError: If JSON is invalid or validation fails.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid selection JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid selection JSON: expected object")
    session = session_from_payload(data)
    validate_session_selection(session)
    return session


def _filter_track_pools(
    track_pools: list[TrackQuestionPools],
    excluded_ids: frozenset[str],
) -> list[TrackQuestionPools]:
    """Remove excluded question IDs from loaded track pools.

    Args:
        track_pools: Loaded pools in selection source order.
        excluded_ids: Question IDs to exclude from planning.

    Returns:
        Pools with excluded IDs removed from full and category pools.
    """
    if not excluded_ids:
        return track_pools
    filtered: list[TrackQuestionPools] = []
    for pools in track_pools:
        filtered.append(
            TrackQuestionPools(
                source=pools.source,
                full_pool=tuple(
                    question
                    for question in pools.full_pool
                    if question.id not in excluded_ids
                ),
                category_pools={
                    category: tuple(
                        question for question in pool if question.id not in excluded_ids
                    )
                    for category, pool in pools.category_pools.items()
                },
            )
        )
    return filtered


def _validate_filtered_pools(
    track_pools: list[TrackQuestionPools],
    question_count: int,
) -> None:
    """Ensure filtered pools can satisfy the requested question count.

    Args:
        track_pools: Pools after excluded-ID filtering.
        question_count: Target number of questions for the session.

    Raises:
        ValueError: If a category is empty or too few questions remain.
    """
    available_ids: set[str] = set()
    for pools in track_pools:
        source = pools.source
        for category in source.categories:
            category_pool = pools.category_pools.get(category, ())
            if not category_pool:
                raise ValueError(
                    f"All questions in {source.track}/{source.level}/{category} "
                    "are marked as known"
                )
        if not pools.full_pool:
            raise ValueError(f"No questions found for {source.track}/{source.level}")
        available_ids.update(question.id for question in pools.full_pool)
    if len(available_ids) < question_count:
        raise ValueError(
            f"Not enough unfamiliar questions: {len(available_ids)} available, "
            f"{question_count} requested"
        )


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
    *,
    excluded_ids: frozenset[str] = frozenset(),
) -> list[PlannedQuestion]:
    """Build ordered question list from pre-loaded pools.

    Picks one random question per selected topic, then fills remaining slots
    proportionally by track pool size. Questions are grouped by track
    (form order) with random order within each block.

    Args:
        selection: Validated interview selection.
        question_count: Target number of questions (>= topic count).
        track_pools: Loaded pools in the same order as ``selection.sources``.
        excluded_ids: Question IDs to remove from pools before planning.

    Returns:
        Ordered list of Question instances.

    Raises:
        ValueError: If pools are empty or misaligned with the selection.
    """
    if len(track_pools) != len(selection.sources):
        raise ValueError("track_pools must match selection.sources")

    filtered_pools = _filter_track_pools(track_pools, excluded_ids)
    _validate_filtered_pools(filtered_pools, question_count)
    track_pools = filtered_pools

    picked: list[PlannedQuestion] = []
    picked_ids: set[str] = set()
    question_track: dict[str, str] = {}
    pools_by_source: list[tuple[TrackSelection, tuple[PlannedQuestion, ...]]] = []

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
        remaining_by_track: list[tuple[str, list[PlannedQuestion]]] = []
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

    by_track: dict[str, list[PlannedQuestion]] = {}
    for question in picked:
        track_key = question_track[question.id]
        by_track.setdefault(track_key, []).append(question)

    ordered: list[PlannedQuestion] = []
    for source in selection.sources:
        block = by_track.get(source.track, [])
        random.shuffle(block)
        ordered.extend(block)

    return ordered[:question_count]
