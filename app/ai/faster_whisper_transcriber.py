# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""faster-whisper implementation of :class:`~app.ai.speech_transcriber.SpeechTranscriber`."""

import asyncio

from faster_whisper import WhisperModel
import numpy as np
import numpy.typing as npt

from app.shared.locales import normalize_locale


class FasterWhisperTranscriber:
    """Transcribe audio using an in-memory ``WhisperModel``."""

    def __init__(self, model: WhisperModel) -> None:
        """Wrap a loaded faster-whisper model.

        Args:
            model: Loaded ``WhisperModel`` instance.
        """
        self._model = model

    async def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        locale: str,
    ) -> str:
        """Transcribe mono float32 audio with VAD filtering.

        Args:
            audio: Mono PCM as float32 samples normalized to [-1, 1].
            locale: Interview locale code for the ``language`` parameter.

        Returns:
            Final recognized text (may be empty).
        """
        language = normalize_locale(locale)

        def _transcribe() -> str:
            segments, _info = self._model.transcribe(
                audio,
                language=language,
                task="transcribe",
                vad_filter=True,
            )
            return "".join(segment.text for segment in segments).strip()

        return await asyncio.to_thread(_transcribe)
