# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test doubles for speech transcription."""

import numpy as np


class FakeTranscriber:
    """Deterministic speech transcriber for tests."""

    def __init__(self, text: str = "spoken answer text") -> None:
        """Initialize with a fixed transcript.

        Args:
            text: Text returned from ``transcribe``.
        """
        self.text = text
        self.last_audio: np.ndarray | None = None
        self.last_locale: str | None = None

    async def transcribe(self, audio: np.ndarray, locale: str) -> str:
        """Store audio samples and return the configured transcript.

        Args:
            audio: Mono float32 samples.
            locale: Interview locale.

        Returns:
            Configured transcript text.
        """
        self.last_audio = audio
        self.last_locale = locale
        return self.text
