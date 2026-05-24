# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview question-bank selection and multi-source question planning."""

from __future__ import annotations

from dataclasses import dataclass
import json
import random
from typing import Any, Protocol

from app.questions import Question

SELECTION_SPEC_VERSION = 1

_LANGUAGE_LABELS: dict[str, str] = {
    "python": "Python",
    "database": "Database / SQL",
}


def language_label(slug: str) -> str:
    """Return a human-readable label for a question-bank language slug.

    Args:
        slug: Language directory name under ``data/questions/``.

    Returns:
        Display label for templates and UI.
    """
    return _LANGUAGE_LABELS.get(slug, slug.replace("-", " ").replace("_", " ").title())


class InterviewSelectionHolder(Protocol):
    """Minimal interview shape for loading ``selection_spec``."""

    id: str
    selection_spec: str


@dataclass(frozen=True)
class LanguageQuestionPools:
    """Loaded question pools for one language source.

    Attributes:
        source: Language, level, and category selection from setup.
        full_pool: All questions across selected categories for the source.
        category_pools: Per-category question lists keyed by category slug.
    """

    source: LanguageSelection
    full_pool: list[Question]
    category_pools: dict[str, list[Question]]


@dataclass(frozen=True)
class LanguageSelection:
    """One programming-language bank with level and topic categories.

    Attributes:
        language: Question bank slug (e.g. ``python``).
        level: Difficulty level (e.g. ``junior``).
        categories: YAML category slugs (e.g. ``basics``, ``oop``).
    """

    language: str
    level: str
    categories: list[str]


@dataclass(frozen=True)
class InterviewSelection:
    """Full interview question-bank selection (one or more languages).

    Attributes:
        sources: Ordered language selections as chosen on the setup form.
    """

    sources: list[LanguageSelection]

    @property
    def topic_count(self) -> int:
        """Return total number of selected categories across all sources."""
        return sum(len(source.categories) for source in self.sources)

    def is_multi(self) -> bool:
        """Return True when more than one language or category is selected."""
        if len(self.sources) > 1:
            return True
        if not self.sources:
            return False
        return len(self.sources[0].categories) > 1


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
        JSON string with version and sources.
    """
    payload = {
        "version": SELECTION_SPEC_VERSION,
        "sources": [
            {
                "language": source.language,
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

    sources: list[LanguageSelection] = []
    for item in sources_raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid selection_spec: source must be an object")
        language = item.get("language")
        level = item.get("level")
        categories = item.get("categories")
        if not isinstance(language, str) or not isinstance(level, str):
            raise ValueError("Invalid selection_spec: language and level required")
        if not isinstance(categories, list) or not categories:
            raise ValueError("Invalid selection_spec: categories required")
        sources.append(
            LanguageSelection(
                language=language,
                level=level,
                categories=[str(c) for c in categories],
            )
        )
    return InterviewSelection(sources=sources)


def selection_sources_summary(selection: InterviewSelection) -> str:
    """Build multi-line sources text for AI evaluation prompts.

    Args:
        selection: Interview selection.

    Returns:
        Bullet list of languages, levels, and categories.
    """
    lines: list[str] = []
    for source in selection.sources:
        label = language_label(source.language)
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
    return f"{language_label(source.language)} Interview"


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
    selection = selection_from_payload(data)
    return selection


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
    language_pools: list[LanguageQuestionPools],
) -> list[Question]:
    """Build ordered question list from pre-loaded pools.

    Picks one random question per selected topic, then fills remaining slots
    proportionally by language pool size. Questions are grouped by language
    (form order) with random order within each block.

    Args:
        selection: Validated interview selection.
        question_count: Target number of questions (>= topic count).
        language_pools: Loaded pools in the same order as ``selection.sources``.

    Returns:
        Ordered list of Question instances.

    Raises:
        ValueError: If pools are empty or misaligned with the selection.
    """
    if len(language_pools) != len(selection.sources):
        raise ValueError("language_pools must match selection.sources")

    picked: list[Question] = []
    picked_ids: set[str] = set()
    question_language: dict[str, str] = {}
    pools_by_source: list[tuple[LanguageSelection, list[Question]]] = []

    for pools in language_pools:
        source = pools.source
        full_pool = pools.full_pool
        if not full_pool:
            raise ValueError(f"No questions found for {source.language}/{source.level}")
        pools_by_source.append((source, full_pool))

        for category in source.categories:
            category_pool = pools.category_pools.get(category, [])
            if not category_pool:
                raise ValueError(
                    f"No questions found for "
                    f"{source.language}/{source.level}/{category}"
                )
            available = [q for q in category_pool if q.id not in picked_ids]
            if not available:
                available = category_pool
            question = random.choice(available)
            picked.append(question)
            picked_ids.add(question.id)
            question_language[question.id] = source.language

    extra = question_count - len(picked)
    if extra > 0:
        remaining_by_lang: list[tuple[str, list[Question]]] = []
        for source, full_pool in pools_by_source:
            remaining_pool = [q for q in full_pool if q.id not in picked_ids]
            if remaining_pool:
                remaining_by_lang.append((source.language, remaining_pool))

        max_extra = sum(len(pool) for _, pool in remaining_by_lang)
        to_allocate = min(extra, max_extra)
        if to_allocate > 0 and remaining_by_lang:
            sizes = [len(pool) for _, pool in remaining_by_lang]
            counts = _allocate_proportional(sizes, to_allocate)
            for (lang, pool), count in zip(remaining_by_lang, counts, strict=True):
                if count <= 0:
                    continue
                sampled = random.sample(pool, min(count, len(pool)))
                picked.extend(sampled)
                for question in sampled:
                    picked_ids.add(question.id)
                    question_language[question.id] = lang

    by_language: dict[str, list[Question]] = {}
    for question in picked:
        lang_key = question_language[question.id]
        by_language.setdefault(lang_key, []).append(question)

    ordered: list[Question] = []
    for source in selection.sources:
        block = by_language.get(source.language, [])
        random.shuffle(block)
        ordered.extend(block)

    return ordered[:question_count]
