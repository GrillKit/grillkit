# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup form template context helpers."""

from collections.abc import Callable

from app.coding.services.availability import is_coding_available
from app.interview.services.rules.bank_selection import track_label
from app.shared import coding as coding_bank
from app.shared.locales import SUPPORTED_LOCALES, normalize_locale
from app.shared.questions import list_categories, list_levels, list_tracks


def _build_track_sections(
    tracks: list[str],
    *,
    list_levels_fn: Callable[[str], list[str]],
    list_categories_fn: Callable[[str, str], list[str]],
) -> list[dict[str, object]]:
    """Build setup track section metadata for one question bank.

    Args:
        tracks: Track slugs from the bank.
        list_levels_fn: Callable ``(track) -> levels``.
        list_categories_fn: Callable ``(track, level) -> categories``.

    Returns:
        Track section dicts for ``setup.html``.
    """
    track_sections: list[dict[str, object]] = []
    for slug in tracks:
        levels = list_levels_fn(slug)
        default_level = levels[0] if levels else ""
        categories = (
            sorted(list_categories_fn(slug, default_level)) if default_level else []
        )
        track_sections.append(
            {
                "slug": slug,
                "label": track_label(slug),
                "levels": levels,
                "default_level": default_level,
                "categories": categories,
            }
        )
    return track_sections


def setup_form_context(
    *,
    locale: str,
    error: str | None = None,
    min_question_count: int = 1,
    min_coding_task_count: int = 1,
    initial_wizard_step: str = "mode",
) -> dict[str, object]:
    """Build template context for the multi-track setup form.

    Args:
        locale: Configured interview locale from provider config.
        error: Optional error message to display.
        min_question_count: Minimum allowed theory question count.
        min_coding_task_count: Minimum allowed coding task count.
        initial_wizard_step: Wizard step id to open on load (``mode``, ``review``, etc.).

    Returns:
        Context dict for ``setup.html``.
    """
    locale_code = normalize_locale(locale)
    locale_label = SUPPORTED_LOCALES[locale_code]
    coding_available = is_coding_available()
    tracks = list_tracks()
    if not tracks:
        return {
            "tracks": [],
            "track_sections": [],
            "coding_track_sections": [],
            "session_modes": [],
            "coding_available": coding_available,
            "locale": locale_code,
            "locale_label": locale_label,
            "error": error or "No question banks found.",
            "min_question_count": min_question_count,
            "min_coding_task_count": min_coding_task_count,
            "initial_wizard_step": initial_wizard_step,
        }

    track_sections = _build_track_sections(
        tracks,
        list_levels_fn=list_levels,
        list_categories_fn=list_categories,
    )
    coding_tracks = coding_bank.list_tracks()
    coding_track_sections = _build_track_sections(
        coding_tracks,
        list_levels_fn=coding_bank.list_levels,
        list_categories_fn=coding_bank.list_categories,
    )

    session_modes = [
        {
            "value": "theory_only",
            "label": "Theory only",
            "description": "Question-and-answer theory section",
            "enabled": True,
        },
        {
            "value": "theory_then_coding",
            "label": "Theory, then coding",
            "description": "Theory section followed by coding challenges",
            "enabled": coding_available,
            "badge": None if coding_available else "Unavailable",
        },
        {
            "value": "coding_then_theory",
            "label": "Coding, then theory",
            "description": "Coding challenges followed by theory questions",
            "enabled": coding_available,
            "badge": None if coding_available else "Unavailable",
        },
        {
            "value": "coding_only",
            "label": "Coding only",
            "description": "Coding challenges without theory questions",
            "enabled": coding_available,
            "badge": None if coding_available else "Unavailable",
        },
    ]

    return {
        "tracks": [(slug, track_label(slug)) for slug in tracks],
        "track_sections": track_sections,
        "coding_track_sections": coding_track_sections,
        "session_modes": session_modes,
        "coding_available": coding_available,
        "locale": locale_code,
        "locale_label": locale_label,
        "error": error,
        "min_question_count": min_question_count,
        "min_coding_task_count": min_coding_task_count,
        "initial_wizard_step": initial_wizard_step,
    }
