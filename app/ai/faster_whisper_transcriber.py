# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""faster-whisper implementation of :class:`~app.ai.speech_transcriber.SpeechTranscriber`."""

import asyncio
import logging

from faster_whisper import WhisperModel
import numpy as np
import numpy.typing as npt

from app.shared.locales import normalize_locale

logger = logging.getLogger(__name__)


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
            segments, info = self._model.transcribe(
                audio,
                language=language,
                task="transcribe",
                vad_filter=False,
            )
            segment_list = list(segments)
            result = "".join((segment.text or "") for segment in segment_list).strip()
            logger.info(
                "Whisper transcript: language=%s segments=%d result=%r",
                getattr(info, "language", language) if info is not None else language,
                len(segment_list),
                result,
            )
            return result

        return await asyncio.to_thread(_transcribe)
