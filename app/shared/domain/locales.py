# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Supported interview locales for AI communication."""

from typing import Final

SUPPORTED_LOCALES: Final[dict[str, str]] = {
    "en": "English",
    "ru": "Russian",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
}

DEFAULT_LOCALE: Final[str] = "en"


def normalize_locale(locale: str) -> str:
    """Return a supported locale code or raise ``ValueError``.

    Args:
        locale: Requested locale code (e.g. ``en``, ``ru``).

    Returns:
        Normalized locale code present in ``SUPPORTED_LOCALES``.

    Raises:
        ValueError: If the locale is not supported.
    """
    code = locale.strip().lower()
    if code not in SUPPORTED_LOCALES:
        supported = ", ".join(sorted(SUPPORTED_LOCALES))
        raise ValueError(f"Unsupported locale '{locale}'. Choose one of: {supported}")
    return code


def language_instruction(locale: str) -> str:
    """Build a system-prompt clause requiring AI output in the given language.

    Args:
        locale: Supported locale code.

    Returns:
        Instruction text appended to evaluator system prompts.
    """
    code = normalize_locale(locale)
    language_name = SUPPORTED_LOCALES[code]
    return (
        f"Conduct this interview in {language_name}. "
        f"All feedback, follow-up questions, and evaluation narrative must be in "
        f"{language_name}. Interview questions from the bank may be in another "
        f"language; still respond in {language_name}. "
        "Keep JSON property names in English. "
        "Return JSON data objects with field values only — never JSON Schema "
        "metadata (no top-level type, properties, description, or $schema)."
    )
