# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview locale helpers."""

import pytest

from app.domain.locales import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    language_instruction,
    normalize_locale,
)


def test_supported_locales_include_requested_codes():
    """All user-facing locale codes are registered."""
    for code in ("en", "ru", "fr", "es", "de"):
        assert code in SUPPORTED_LOCALES


def test_normalize_locale_accepts_known_code():
    """normalize_locale returns lowercase code for supported locales."""
    assert normalize_locale("RU") == "ru"
    assert normalize_locale(" de ") == "de"


def test_normalize_locale_rejects_unknown():
    """normalize_locale raises for unsupported locales."""
    with pytest.raises(ValueError, match="Unsupported locale"):
        normalize_locale("xx")


def test_language_instruction_mentions_language_name():
    """Prompt clause names the target language."""
    text = language_instruction("ru")
    assert "Russian" in text
    assert DEFAULT_LOCALE == "en"


def test_language_instruction_warns_against_schema_metadata():
    """Prompt clause tells the model not to return JSON Schema metadata."""
    text = language_instruction("en")
    assert "JSON Schema" in text
    assert "metadata" in text
