# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech-to-text transcriber protocol for offline dictation."""

from typing import Protocol

import numpy as np
import numpy.typing as npt


class SpeechTranscriber(Protocol):
    """Transcribe mono float32 audio into text for a given locale."""

    async def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        locale: str,
    ) -> str:
        """Transcribe audio samples and return the full transcript.

        Args:
            audio: Mono PCM as float32 samples normalized to [-1, 1].
            locale: Interview locale code for the recognition language.

        Returns:
            Final recognized text (may be empty).
        """
        ...
