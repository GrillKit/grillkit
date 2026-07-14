# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Resolve known bank item IDs to their question text from the YAML banks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.shared import coding as coding_bank
from app.shared import questions as theory_bank


@dataclass(frozen=True, slots=True)
class KnownQuestionView:
    """Display row for a known bank item on the management page.

    Attributes:
        id: Bank item ID from the YAML bank.
        text: Resolved question or task text, or the ID when unresolved.
    """

    id: str
    text: str


@lru_cache(maxsize=1)
def _theory_text_index() -> dict[str, str]:
    """Build an ``id -> text`` map across the whole theory bank.

    The result is cached for the process lifetime: the YAML banks ship with the
    image and do not change at runtime, so parsing every file on each request is
    unnecessary. The returned mapping is read-only for callers.

    Returns:
        Mapping of theory question IDs to their text (first occurrence wins).
    """
    index: dict[str, str] = {}
    for track in theory_bank.list_tracks():
        for level in theory_bank.list_levels(track):
            for category in theory_bank.list_categories(track, level):
                for question in theory_bank.load_category(track, level, category):
                    index.setdefault(question.id, question.text)
    return index


@lru_cache(maxsize=1)
def _coding_text_index() -> dict[str, str]:
    """Build an ``id -> text`` map across the whole coding bank.

    The result is cached for the process lifetime: the YAML banks ship with the
    image and do not change at runtime, so parsing every file on each request is
    unnecessary. The returned mapping is read-only for callers.

    Returns:
        Mapping of coding task IDs to their text (first occurrence wins).
    """
    index: dict[str, str] = {}
    for track in coding_bank.list_tracks():
        for level in coding_bank.list_levels(track):
            for category in coding_bank.list_categories(track, level):
                for task in coding_bank.load_category(track, level, category):
                    index.setdefault(task.id, task.text)
    return index


def _to_views(item_ids: list[str], index: dict[str, str]) -> list[KnownQuestionView]:
    """Map bank item IDs to display rows using a text index.

    Args:
        item_ids: Bank item IDs marked as known.
        index: ``id -> text`` map for the matching bank.

    Returns:
        Display rows; the ID is used as text when it is missing from the bank.
    """
    return [
        KnownQuestionView(id=item_id, text=index.get(item_id, item_id))
        for item_id in item_ids
    ]


def resolve_known_views(
    grouped: dict[str, list[str]],
) -> dict[str, list[KnownQuestionView]]:
    """Enrich grouped known item IDs with their bank text.

    Args:
        grouped: Known item IDs grouped by ``theory`` and ``coding`` branches.

    Returns:
        Display rows grouped by the same branches.
    """
    return {
        "theory": _to_views(grouped.get("theory", []), _theory_text_index()),
        "coding": _to_views(grouped.get("coding", []), _coding_text_index()),
    }
