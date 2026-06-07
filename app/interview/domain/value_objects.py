# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PlannedQuestion:
    """Question snapshot used when starting an interview session.

    Attributes:
        id: Unique question identifier from the question bank.
        text: Localized question text shown to the user.
        code: Optional code snippet, or None when not applicable.
    """

    id: str
    text: str
    code: str | None


class InterviewSelectionHolder(Protocol):
    """Minimal interview shape for loading ``selection_spec`` from persistence."""

    id: str
    selection_spec: str


@dataclass(frozen=True, slots=True)
class TrackSelection:
    """One question-bank track with level and topic categories.

    Attributes:
        track: Question bank slug (e.g. ``python``).
        level: Difficulty level (e.g. ``junior``).
        categories: YAML category slugs (e.g. ``basics``, ``oop``).
    """

    track: str
    level: str
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InterviewSelection:
    """Full interview question-bank selection (one or more tracks).

    Attributes:
        sources: Ordered track selections as chosen on the setup form.
    """

    sources: tuple[TrackSelection, ...]

    @property
    def topic_count(self) -> int:
        """Return total number of selected categories across all sources."""
        return sum(len(source.categories) for source in self.sources)

    def is_multi(self) -> bool:
        """Return True when more than one track or category is selected."""
        if len(self.sources) > 1:
            return True
        if not self.sources:
            return False
        return len(self.sources[0].categories) > 1


@dataclass(frozen=True, slots=True)
class TrackQuestionPools:
    """Loaded question pools for one track source.

    Attributes:
        source: Track, level, and category selection from setup.
        full_pool: All questions across selected categories for the source.
        category_pools: Per-category question lists keyed by category slug.
    """

    source: TrackSelection
    full_pool: tuple[PlannedQuestion, ...]
    category_pools: dict[str, tuple[PlannedQuestion, ...]]
