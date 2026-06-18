# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for FasterWhisperTranscriber."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.ai.faster_whisper_transcriber import FasterWhisperTranscriber


class FakeSegment:
    """Fake segment matching faster-whisper segment interface."""

    def __init__(self, text):
        self.text = text


class TestFasterWhisperTranscriber:
    """Tests for the faster-whisper adapter."""

    @pytest.mark.asyncio
    async def test_transcribe_calls_model_transcribe(self):
        """Adapter delegates to WhisperModel.transcribe with correct arguments."""
        segment = FakeSegment(" hello world")
        model = MagicMock()
        model.transcribe.return_value = ([segment], None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(16000, dtype=np.float32)
        text = await transcriber.transcribe(audio, "en")

        assert text == "hello world"
        model.transcribe.assert_called_once()
        call_args, call_kwargs = model.transcribe.call_args
        assert call_args[0] is audio
        assert call_kwargs["language"] == "en"
        assert call_kwargs["task"] == "transcribe"

    @pytest.mark.asyncio
    async def test_uses_vad_filter_true(self):
        """Transcription enables VAD filtering."""
        segment = FakeSegment(" test")
        model = MagicMock()
        model.transcribe.return_value = ([segment], None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(8000, dtype=np.float32)
        await transcriber.transcribe(audio, "ru")

        call_kwargs = model.transcribe.call_args.kwargs
        assert call_kwargs["vad_filter"] is True

    @pytest.mark.asyncio
    async def test_normalizes_locale(self):
        """Locale is normalized before being passed to the model."""
        segment = FakeSegment(" result")
        model = MagicMock()
        model.transcribe.return_value = ([segment], None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(8000, dtype=np.float32)
        text = await transcriber.transcribe(audio, " RU ")

        call_kwargs = model.transcribe.call_args.kwargs
        assert call_kwargs["language"] == "ru"
        assert text == "result"

    @pytest.mark.asyncio
    async def test_joins_multiple_segments(self):
        """Multiple segments are concatenated and stripped."""
        segments = [FakeSegment(" Hello"), FakeSegment(" world")]
        model = MagicMock()
        model.transcribe.return_value = (segments, None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(8000, dtype=np.float32)
        text = await transcriber.transcribe(audio, "en")

        assert text == "Hello world"

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_segments(self):
        """Empty segment list produces empty transcript."""
        model = MagicMock()
        model.transcribe.return_value = ([], None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(8000, dtype=np.float32)
        text = await transcriber.transcribe(audio, "en")

        assert text == ""

    @pytest.mark.asyncio
    async def test_runs_in_thread(self):
        """Transcription runs the blocking model in a thread."""
        segment = FakeSegment(" async result")
        model = MagicMock()
        model.transcribe.return_value = ([segment], None)

        with patch(
            "asyncio.to_thread", side_effect=lambda f, *a, **k: f(*a, **k)
        ) as mock_to_thread:  # noqa: E501
            transcriber = FasterWhisperTranscriber(model)
            audio = np.zeros(8000, dtype=np.float32)
            await transcriber.transcribe(audio, "en")

        mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_strips_whitespace(self):
        """Trailing and leading whitespace is stripped from result."""
        segments = [FakeSegment("  padded  ")]
        model = MagicMock()
        model.transcribe.return_value = (segments, None)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(8000, dtype=np.float32)
        text = await transcriber.transcribe(audio, "en")

        assert text == "padded"

    @pytest.mark.asyncio
    async def test_ignores_info_return_value(self):
        """Second return value from transcribe (info) is ignored."""
        segment = FakeSegment("text")
        info = MagicMock()
        info.language = "en"
        model = MagicMock()
        model.transcribe.return_value = ([segment], info)

        transcriber = FasterWhisperTranscriber(model)
        audio = np.zeros(8000, dtype=np.float32)
        text = await transcriber.transcribe(audio, "en")

        assert text == "text"
