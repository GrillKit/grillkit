# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SpeechTranscriber protocol."""

import inspect
from typing import Protocol, get_type_hints

import numpy as np
import pytest

from app.ai.speech_transcriber import SpeechTranscriber


class TestSpeechTranscriber:
    """Tests for the SpeechTranscriber protocol structure."""

    def test_is_protocol(self):
        """SpeechTranscriber is a typing Protocol."""
        assert issubclass(SpeechTranscriber, Protocol)

    def test_has_transcribe_method(self):
        """Protocol defines a transcribe method."""
        assert hasattr(SpeechTranscriber, "transcribe")
        assert inspect.isfunction(SpeechTranscriber.transcribe)

    def test_transcribe_signature(self):
        """transcribe accepts audio and locale parameters."""
        hints = get_type_hints(SpeechTranscriber.transcribe)
        assert "audio" in hints
        assert "locale" in hints
        assert "return" in hints
        assert hints["return"] is str

    def test_fake_transcriber_has_transcribe_method(self):
        """Fake transcriber used in other tests has the required method."""
        from tests.helpers.transcription import FakeTranscriber

        fake = FakeTranscriber("test")
        assert hasattr(fake, "transcribe")
        assert inspect.iscoroutinefunction(fake.transcribe)

    @pytest.mark.asyncio
    async def test_fake_transcriber_awaitable(self):
        """Fake transcriber transcribe method is awaitable."""
        from tests.helpers.transcription import FakeTranscriber

        fake = FakeTranscriber("test result")
        audio = np.zeros(1600, dtype=np.float32)
        result = await fake.transcribe(audio, "en")
        assert result == "test result"
