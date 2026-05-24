# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""In-process speech transcriber loading and hot-reload."""

import logging
import os
from typing import ClassVar

from fastapi import FastAPI
from faster_whisper import WhisperModel

from app.ai.faster_whisper_transcriber import FasterWhisperTranscriber
from app.ai.speech_transcriber import SpeechTranscriber
from app.shared.infrastructure.in_process_runtime import InProcessArtifactRuntime
from app.speech.domain.models import normalize_speech_model_size
from app.speech.services.whisper_storage import is_installed, model_dir

logger = logging.getLogger(__name__)

WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


class WhisperRuntime(InProcessArtifactRuntime):
    """Hold the loaded :class:`SpeechTranscriber` and sync it to ``app.state``."""

    _app: ClassVar[FastAPI | None] = None

    @classmethod
    def normalize_key(cls, key: str) -> str:
        """Normalize a speech model size identifier."""
        return normalize_speech_model_size(key)

    @classmethod
    def is_installed(cls, key: str) -> bool:
        """Return whether a valid Whisper model is on disk for ``key``."""
        return is_installed(key)

    @classmethod
    def load_sync(cls, key: str) -> SpeechTranscriber:
        """Load ``WhisperModel`` and wrap it in a transcriber (blocking)."""
        path = model_dir(key)
        model = WhisperModel(
            str(path),
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        return FasterWhisperTranscriber(model)

    @classmethod
    def bind_app(cls, app: FastAPI) -> None:
        """Register the FastAPI app for ``app.state`` updates after load/unload."""
        cls._app = app

    @classmethod
    def loaded_size(cls) -> str | None:
        """Return the size of the model currently in memory, if any."""
        return cls.loaded_key()

    @classmethod
    async def load_size(cls, size: str) -> bool:
        """Load or reload the Whisper model for ``size`` from disk.

        Args:
            size: Speech model size identifier.

        Returns:
            True if a transcriber is loaded for the size after this call.
        """
        loaded = await cls.load(size)
        if loaded:
            logger.info(
                "Loaded Whisper model %s from %s",
                cls.normalize_key(size),
                model_dir(cls.normalize_key(size)),
            )
        return loaded

    @classmethod
    def on_loaded(cls, key: str, artifact: SpeechTranscriber) -> None:
        """Mirror runtime handles onto the bound FastAPI application."""
        del artifact
        cls._sync_app_state()

    @classmethod
    def on_unloaded(cls) -> None:
        """Clear ``app.state`` when the transcriber is dropped."""
        cls._sync_app_state()

    @classmethod
    def _sync_app_state(cls) -> None:
        """Mirror runtime handles onto the bound FastAPI application."""
        app = cls._app
        if app is None:
            return
        app.state.speech_transcriber = cls._artifact
