# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for dictation speech recognition."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.faster_whisper_transcriber import FasterWhisperTranscriber
from app.services.speech_recognition import DictationSession


class FakeTranscriber:
    """Minimal transcriber for dictation session tests."""

    def __init__(self, text: str = "hello") -> None:
        """Store the transcript to return."""
        self.text = text
        self.last_audio: np.ndarray | None = None
        self.last_locale: str | None = None

    async def transcribe(self, audio: np.ndarray, locale: str) -> str:
        """Record inputs and return a fixed transcript."""
        self.last_audio = audio
        self.last_locale = locale
        return self.text


class TestDictationSession:
    """Tests for buffered PCM transcription."""

    @pytest.mark.asyncio
    async def test_finalize_empty_buffer(self):
        """Empty buffer returns an empty transcript without calling the transcriber."""
        session = DictationSession()
        transcriber = FakeTranscriber("ignored")
        text = await session.finalize(transcriber, "en")
        assert text == ""
        assert transcriber.last_audio is None

    @pytest.mark.asyncio
    async def test_finalize_uses_transcriber(self):
        """Buffered PCM is passed to the transcriber with the interview locale."""
        session = DictationSession()
        samples = (np.zeros(1600, dtype=np.int16)).tobytes()
        session.append_pcm(samples)

        transcriber = FakeTranscriber("hello")
        text = await session.finalize(transcriber, "ru")
        assert text == "hello"
        assert transcriber.last_locale == "ru"
        assert transcriber.last_audio is not None
        assert transcriber.last_audio.dtype == np.float32
        assert len(transcriber.last_audio) == 1600


class TestFasterWhisperTranscriber:
    """Tests for the faster-whisper adapter."""

    @pytest.mark.asyncio
    async def test_transcribe_calls_model(self):
        """Adapter delegates to WhisperModel.transcribe with locale language."""
        segment = MagicMock()
        segment.text = " hello"
        model = MagicMock()
        model.transcribe.return_value = ([segment], None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(1600, dtype=np.float32)
        text = await transcriber.transcribe(audio, "ru")

        assert text == "hello"
        model.transcribe.assert_called_once()
        call_kwargs = model.transcribe.call_args.kwargs
        assert call_kwargs["language"] == "ru"
        assert call_kwargs["task"] == "transcribe"
