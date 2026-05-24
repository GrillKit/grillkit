# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TTS disk cache helpers."""

from unittest.mock import AsyncMock, patch

import pytest

from app.question_voice.domain.tts_exceptions import QuestionVoiceSynthesisError
from app.question_voice.domain.voices import DEFAULT_TTS_VOICE_ID
from app.question_voice.services.tts_cache import TtsCacheService


class TestTtsCacheService:
    """Cache key and fetch behavior."""

    def test_normalize_text_collapses_whitespace(self):
        """Whitespace normalization is stable for hashing."""
        assert TtsCacheService.normalize_text("  Hello \n world  ") == "Hello world"

    def test_cache_path_uses_locale_and_hash(self, tmp_path, monkeypatch):
        """Cache files live under locale-specific directories."""
        monkeypatch.setattr(
            "app.question_voice.services.tts_cache.TTS_CACHE_DIR", tmp_path
        )
        path = TtsCacheService.cache_path("ru", "Same text")
        assert path.parent == tmp_path / "v2" / "ru"
        assert path.suffix == ".wav"
        again = TtsCacheService.cache_path("ru", "Same  text")
        assert path == again

    @pytest.mark.asyncio
    async def test_get_or_fetch_returns_existing_file(self, tmp_path, monkeypatch):
        """Cache hit does not call Piper synthesis."""
        monkeypatch.setattr(
            "app.question_voice.services.tts_cache.TTS_CACHE_DIR", tmp_path
        )
        path = TtsCacheService.cache_path("en", "Question?")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF")
        with patch(
            "app.question_voice.services.tts_cache.PiperRuntime.synthesize_wav_bytes",
            new_callable=AsyncMock,
        ) as mock_synth:
            result = await TtsCacheService.get_or_fetch(
                DEFAULT_TTS_VOICE_ID, "en", "Question?"
            )
        assert result == path
        mock_synth.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_fetch_writes_on_miss(self, tmp_path, monkeypatch):
        """Cache miss synthesizes audio and stores WAV bytes."""
        monkeypatch.setattr(
            "app.question_voice.services.tts_cache.TTS_CACHE_DIR", tmp_path
        )
        with (
            patch(
                "app.question_voice.services.tts_cache.is_voice_installed",
                return_value=True,
            ),
            patch(
                "app.question_voice.services.tts_cache.PiperRuntime.is_loaded",
                return_value=True,
            ),
            patch(
                "app.question_voice.services.tts_cache.PiperRuntime.synthesize_wav_bytes",
                new_callable=AsyncMock,
                return_value=b"WAVDATA",
            ),
        ):
            path = await TtsCacheService.get_or_fetch(
                DEFAULT_TTS_VOICE_ID, "en", "Hello?"
            )
        assert path.is_file()
        assert path.read_bytes() == b"WAVDATA"

    @pytest.mark.asyncio
    async def test_get_or_fetch_unavailable_when_voice_missing(
        self, tmp_path, monkeypatch
    ):
        """Missing Piper voice raises QuestionVoiceSynthesisError."""
        monkeypatch.setattr(
            "app.question_voice.services.tts_cache.TTS_CACHE_DIR", tmp_path
        )
        with (
            patch(
                "app.question_voice.services.tts_cache.is_voice_installed",
                return_value=False,
            ),
            pytest.raises(QuestionVoiceSynthesisError),
        ):
            await TtsCacheService.get_or_fetch(DEFAULT_TTS_VOICE_ID, "en", "Hello?")
