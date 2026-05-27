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

TIMEOUT_FEEDBACK_MESSAGES: Final[dict[str, str]] = {
    "en": "Time expired. You received 0 points for this answer.",
    "ru": "Время вышло. За этот ответ начислено 0 баллов.",
    "fr": "Le temps est écoulé. Vous avez reçu 0 point pour cette réponse.",
    "es": "Se agotó el tiempo. Has recibido 0 puntos por esta respuesta.",
    "de": "Die Zeit ist abgelaufen. Für diese Antwort wurden 0 Punkte vergeben.",
}

TIMEOUT_CHAT_LABELS: Final[dict[str, str]] = {
    "en": "Time expired — 0 points",
    "ru": "Время вышло — 0 баллов",
    "fr": "Temps écoulé — 0 point",
    "es": "Tiempo agotado — 0 puntos",
    "de": "Zeit abgelaufen — 0 Punkte",
}


def localized_string(locale: str, messages: dict[str, str]) -> str:
    """Return a UI string for the locale, falling back to ``DEFAULT_LOCALE``.

    Args:
        locale: Interview locale code (normalized if supported).
        messages: Mapping of locale code to translated text.

    Returns:
        Message for the locale, or the default locale when unknown.
    """
    try:
        code = normalize_locale(locale)
    except ValueError:
        code = DEFAULT_LOCALE
    return messages.get(code, messages[DEFAULT_LOCALE])


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
