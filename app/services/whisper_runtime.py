# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""In-process speech transcriber loading and hot-reload."""

import asyncio
import logging
import os
from pathlib import Path
from typing import ClassVar

from fastapi import FastAPI
from faster_whisper import WhisperModel

from app.ai.speech_transcriber import SpeechTranscriber
from app.domain.speech_models import normalize_speech_model_size
from app.services.faster_whisper_transcriber import FasterWhisperTranscriber
from app.services.whisper_storage import is_installed, model_dir

logger = logging.getLogger(__name__)

WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


class WhisperRuntime:
    """Hold the loaded :class:`SpeechTranscriber` and sync it to ``app.state``."""

    _transcriber: ClassVar[SpeechTranscriber | None] = None
    _size: ClassVar[str | None] = None
    _load_error: ClassVar[str | None] = None
    _app: ClassVar[FastAPI | None] = None

    @staticmethod
    def bind_app(app: FastAPI) -> None:
        """Register the FastAPI app for ``app.state`` updates after load/unload."""
        WhisperRuntime._app = app

    @staticmethod
    def loaded_size() -> str | None:
        """Return the size of the model currently in memory, if any."""
        return WhisperRuntime._size

    @staticmethod
    def is_loaded(size: str) -> bool:
        """Return whether a speech model for ``size`` is loaded in this process."""
        if WhisperRuntime._transcriber is None or WhisperRuntime._size is None:
            return False
        return WhisperRuntime._size == normalize_speech_model_size(size)

    @staticmethod
    def load_error() -> str | None:
        """Return the last in-process load error message, if any."""
        return WhisperRuntime._load_error

    @staticmethod
    async def load_size(size: str) -> bool:
        """Load or reload the Whisper model for ``size`` from disk.

        Args:
            size: Speech model size identifier.

        Returns:
            True if a transcriber is loaded for the size after this call.
        """
        code = normalize_speech_model_size(size)
        path = model_dir(code)
        if not is_installed(code):
            WhisperRuntime.unload()
            WhisperRuntime._load_error = None
            return False

        try:
            model = await asyncio.to_thread(
                WhisperRuntime._load_model_sync,
                path,
            )
        except Exception as exc:
            logger.exception("Failed to load Whisper model for size %s", code)
            WhisperRuntime.unload()
            WhisperRuntime._load_error = str(exc)
            return False

        WhisperRuntime._transcriber = FasterWhisperTranscriber(model)
        WhisperRuntime._size = code
        WhisperRuntime._load_error = None
        WhisperRuntime._sync_app_state()
        logger.info("Loaded Whisper model %s from %s", code, path)
        return True

    @staticmethod
    def unload() -> None:
        """Drop the in-memory transcriber and clear ``app.state``."""
        WhisperRuntime._transcriber = None
        WhisperRuntime._size = None
        WhisperRuntime._sync_app_state()

    @staticmethod
    def _load_model_sync(model_path: Path) -> WhisperModel:
        """Load ``WhisperModel`` from a local snapshot directory (blocking)."""
        return WhisperModel(
            str(model_path),
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

    @staticmethod
    def _sync_app_state() -> None:
        """Mirror runtime handles onto the bound FastAPI application."""
        app = WhisperRuntime._app
        if app is None:
            return
        app.state.speech_transcriber = WhisperRuntime._transcriber
