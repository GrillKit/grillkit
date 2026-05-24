# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup form template context helpers."""

from app.interview.domain.selection import language_label
from app.questions import list_categories, list_languages, list_levels
from app.shared.domain.locales import SUPPORTED_LOCALES, normalize_locale


def setup_form_context(
    *,
    locale: str,
    error: str | None = None,
    min_question_count: int = 1,
) -> dict[str, object]:
    """Build template context for the multi-language setup form.

    Args:
        locale: Configured interview language code from provider config.
        error: Optional error message to display.
        min_question_count: Minimum allowed question count (updated client-side).

    Returns:
        Context dict for ``setup.html``.
    """
    locale_code = normalize_locale(locale)
    locale_label = SUPPORTED_LOCALES[locale_code]
    languages = list_languages()
    if not languages:
        return {
            "languages": [],
            "language_sections": [],
            "locale": locale_code,
            "locale_label": locale_label,
            "error": error or "No question banks found.",
            "min_question_count": min_question_count,
        }

    language_sections: list[dict[str, object]] = []
    for slug in languages:
        levels = list_levels(slug)
        default_level = levels[0] if levels else ""
        categories = (
            sorted(list_categories(slug, default_level)) if default_level else []
        )
        language_sections.append(
            {
                "slug": slug,
                "label": language_label(slug),
                "levels": levels,
                "default_level": default_level,
                "categories": categories,
            }
        )

    return {
        "languages": [(slug, language_label(slug)) for slug in languages],
        "language_sections": language_sections,
        "locale": locale_code,
        "locale_label": locale_label,
        "error": error,
        "min_question_count": min_question_count,
    }
