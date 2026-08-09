# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for dictation speech recognition."""

import numpy as np
import pytest

from app.speech.use_cases.dictation import DictationSession
from tests.helpers.transcription import FakeTranscriber


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
