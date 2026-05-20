# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup form template context helpers."""

from app.domain.locales import SUPPORTED_LOCALES, normalize_locale
from app.questions import list_categories, list_languages, list_levels

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


def setup_form_context(
    *,
    locale: str,
    language: str | None = None,
    level: str | None = None,
    error: str | None = None,
) -> dict[str, object]:
    """Build template context for the setup form with cascaded options.

    Args:
        locale: Configured interview language code from provider config.
        language: Selected programming language slug.
        level: Selected difficulty level.
        error: Optional error message to display.

    Returns:
        Context dict for ``setup.html``.
    """
    locale_code = normalize_locale(locale)
    locale_label = SUPPORTED_LOCALES[locale_code]
    languages = list_languages()
    if not languages:
        return {
            "languages": [],
            "levels": [],
            "categories": [],
            "selected_language": "",
            "selected_level": "",
            "locale": locale_code,
            "locale_label": locale_label,
            "error": error or "No question banks found.",
        }

    selected_language = language if language in languages else languages[0]
    levels = list_levels(selected_language)
    selected_level = level if level in levels else (levels[0] if levels else "")
    categories = (
        sorted(list_categories(selected_language, selected_level))
        if selected_level
        else []
    )

    return {
        "languages": [(slug, language_label(slug)) for slug in languages],
        "levels": levels,
        "categories": categories,
        "selected_language": selected_language,
        "selected_level": selected_level,
        "locale": locale_code,
        "locale_label": locale_label,
        "error": error,
    }
