# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Dictation session for buffered PCM audio."""

import numpy as np

from app.ai.speech_transcriber import SpeechTranscriber

DICTATION_SAMPLE_RATE_HZ: int = 16000


class DictationSession:
    """Buffered PCM audio transcribed on finalize via a :class:`SpeechTranscriber`.

    Expects 16-bit signed little-endian mono PCM at ``DICTATION_SAMPLE_RATE_HZ``.
    """

    def __init__(self) -> None:
        """Create an empty dictation buffer."""
        self._buffer = bytearray()

    def append_pcm(self, chunk: bytes) -> None:
        """Append raw PCM samples to the session buffer.

        Args:
            chunk: Raw 16-bit LE mono PCM samples.
        """
        if chunk:
            self._buffer.extend(chunk)

    async def finalize(self, transcriber: SpeechTranscriber, locale: str) -> str:
        """Transcribe buffered audio and return the full transcript.

        Args:
            transcriber: Loaded speech transcriber implementation.
            locale: Interview locale code for recognition language.

        Returns:
            Final recognized text (may be empty).
        """
        if not self._buffer:
            return ""

        audio = (
            np.frombuffer(bytes(self._buffer), dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        return await transcriber.transcribe(audio, locale)
