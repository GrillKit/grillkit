# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

SessionMode = Literal[
    "theory_only",
    "coding_only",
    "theory_then_coding",
    "coding_then_theory",
]

SESSION_MODE_LABELS: dict[SessionMode, str] = {
    "theory_only": "Theory",
    "coding_only": "Coding",
    "theory_then_coding": "Theory → Coding",
    "coding_then_theory": "Coding → Theory",
}

SESSION_MODE_BADGE_LABELS: dict[SessionMode, str] = {
    "theory_only": "Theory",
    "coding_only": "Coding",
    "theory_then_coding": "Theory+Coding",
    "coding_then_theory": "Theory+Coding",
}


def session_mode_label(mode: SessionMode) -> str:
    """Return a short dashboard badge label for a session mode.

    Args:
        mode: Session mode from setup or persistence.

    Returns:
        Compact human-readable mode badge text.
    """
    return SESSION_MODE_BADGE_LABELS.get(mode, "Theory")


@dataclass(frozen=True, slots=True)
class PlannedQuestion:
    """Question snapshot used when starting an interview session.

    Attributes:
        id: Unique question identifier from the question bank.
        text: Localized question text shown to the user.
        code: Optional code snippet, or None when not applicable.
        expected_points: Rubric bullets for AI evaluation.
    """

    id: str
    text: str
    code: str | None
    expected_points: tuple[str, ...] = ()


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
class SectionBranchSpec:
    """Configuration for one session section branch (theory or coding).

    Attributes:
        enabled: Whether this branch is active for the session mode.
        question_count: Number of questions or tasks in the branch.
        task_time_limit_seconds: Per-round time limit, or None when disabled.
        sources: Question-bank track selections for this branch.
    """

    enabled: bool
    question_count: int
    task_time_limit_seconds: int | None
    sources: tuple[TrackSelection, ...]

    @property
    def topic_count(self) -> int:
        """Return total number of selected categories across all sources."""
        return sum(len(source.categories) for source in self.sources)


@dataclass(frozen=True, slots=True)
class SessionSelection:
    """Full session setup including mode and per-section configuration.

    Attributes:
        session_mode: How theory and coding sections are ordered and enabled.
        theory: Theory section branch configuration.
        coding: Coding section branch configuration (stub until coding plan).
    """

    session_mode: SessionMode
    theory: SectionBranchSpec
    coding: SectionBranchSpec

    @classmethod
    def theory_only(
        cls,
        *,
        sources: tuple[TrackSelection, ...],
        question_count: int = 5,
        task_time_limit_seconds: int | None = None,
    ) -> SessionSelection:
        """Build a theory-only session selection.

        Args:
            sources: Track/level/topic selections for theory.
            question_count: Number of theory questions.
            task_time_limit_seconds: Per-round time limit, or None to disable.

        Returns:
            Session selection with coding disabled.
        """
        return cls(
            session_mode="theory_only",
            theory=SectionBranchSpec(
                enabled=True,
                question_count=question_count,
                task_time_limit_seconds=task_time_limit_seconds,
                sources=sources,
            ),
            coding=SectionBranchSpec(
                enabled=False,
                question_count=0,
                task_time_limit_seconds=None,
                sources=(),
            ),
        )

    @property
    def theory_selection(self) -> InterviewSelection:
        """Return theory sources as a legacy interview selection."""
        return InterviewSelection(sources=self.theory.sources)

    @property
    def coding_selection(self) -> InterviewSelection:
        """Return coding sources as an interview selection."""
        return InterviewSelection(sources=self.coding.sources)


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
