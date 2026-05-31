# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup form template context helpers."""

from app.interview.services.rules.selection import track_label
from app.questions import list_categories, list_levels, list_tracks
from app.shared.locales import SUPPORTED_LOCALES, normalize_locale


def setup_form_context(
    *,
    locale: str,
    error: str | None = None,
    min_question_count: int = 1,
) -> dict[str, object]:
    """Build template context for the multi-track setup form.

    Args:
        locale: Configured interview locale from provider config.
        error: Optional error message to display.
        min_question_count: Minimum allowed question count (updated client-side).

    Returns:
        Context dict for ``setup.html``.
    """
    locale_code = normalize_locale(locale)
    locale_label = SUPPORTED_LOCALES[locale_code]
    tracks = list_tracks()
    if not tracks:
        return {
            "tracks": [],
            "track_sections": [],
            "locale": locale_code,
            "locale_label": locale_label,
            "error": error or "No question banks found.",
            "min_question_count": min_question_count,
        }

    track_sections: list[dict[str, object]] = []
    for slug in tracks:
        levels = list_levels(slug)
        default_level = levels[0] if levels else ""
        categories = (
            sorted(list_categories(slug, default_level)) if default_level else []
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

    return {
        "tracks": [(slug, track_label(slug)) for slug in tracks],
        "track_sections": track_sections,
        "locale": locale_code,
        "locale_label": locale_label,
        "error": error,
        "min_question_count": min_question_count,
    }
