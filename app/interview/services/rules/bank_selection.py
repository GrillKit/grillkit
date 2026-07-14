# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared validation for theory and coding YAML bank selections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.interview.domain.value_objects import InterviewSelection

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


@dataclass(frozen=True, slots=True)
class BankCatalog:
    """Filesystem accessors for a YAML question or coding task bank.

    Attributes:
        list_tracks: Return top-level track slugs.
        list_levels: Return level slugs for a track.
        list_categories: Return category slugs for a track and level.
    """

    list_tracks: Callable[[], list[str]]
    list_levels: Callable[[str], list[str]]
    list_categories: Callable[[str, str], list[str]]


@dataclass(frozen=True, slots=True)
class BankSelectionMessages:
    """User-facing validation messages for a bank selection.

    Attributes:
        empty_sources: Raised when no track sources are selected.
        unknown_track: Format an unknown track slug.
        unknown_level: Format an unknown level for a track.
        empty_categories: Format a missing topic selection for a track.
        unknown_category: Format an unknown topic for a track and level.
    """

    empty_sources: str
    unknown_track: Callable[[str], str]
    unknown_level: Callable[[str, str], str]
    empty_categories: Callable[[str], str]
    unknown_category: Callable[[str, str, str], str]


def validate_bank_selection(
    selection: InterviewSelection,
    catalog: BankCatalog,
    messages: BankSelectionMessages,
) -> None:
    """Validate selection against an on-disk YAML bank layout.

    Args:
        selection: Parsed interview branch selection.
        catalog: Bank filesystem accessors.
        messages: User-facing error message templates.

    Raises:
        ValueError: If selection is empty or references unknown bank paths.
    """
    if not selection.sources:
        raise ValueError(messages.empty_sources)

    tracks = set(catalog.list_tracks())
    for source in selection.sources:
        if source.track not in tracks:
            raise ValueError(messages.unknown_track(source.track))
        levels = set(catalog.list_levels(source.track))
        if source.level not in levels:
            raise ValueError(messages.unknown_level(source.level, source.track))
        if not source.categories:
            raise ValueError(messages.empty_categories(source.track))
        available = set(catalog.list_categories(source.track, source.level))
        for category in source.categories:
            if category not in available:
                raise ValueError(
                    messages.unknown_category(
                        category,
                        source.track,
                        source.level,
                    )
                )
