# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Whisper speech model download and on-disk installation."""

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
from typing import ClassVar, Literal

from huggingface_hub import snapshot_download

from app.domain.locales import SUPPORTED_LOCALES, normalize_locale
from app.domain.speech_models import (
    SpeechModelSpec,
    normalize_speech_model_size,
    speech_model_spec_for_size,
)
from app.paths import WHISPER_MODELS_ROOT
from app.services.whisper_runtime import WhisperRuntime
from app.services.whisper_storage import is_installed, is_valid_model_dir, model_dir

logger = logging.getLogger(__name__)

WhisperModelState = Literal["missing", "ready", "downloading", "error"]


@dataclass
class WhisperModelStatus:
    """Runtime status of the Whisper model for one size and locale.

    Attributes:
        size: Speech model size identifier.
        locale: Interview locale used for transcription language.
        locale_label: Display name for the locale.
        state: Installation or download state.
        percent: Download progress 0–100 when ``state`` is ``downloading``.
        message: User-facing status or error text.
        model_display_name: Whisper package label for UI.
        loaded_in_memory: True when ``WhisperModel`` is loaded for this size.
    """

    size: str
    locale: str
    locale_label: str
    state: WhisperModelState
    percent: int
    message: str
    model_display_name: str
    loaded_in_memory: bool = False


class WhisperModelService:
    """Download and verify offline Whisper models under ``data/whisper-models/``."""

    _download_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _active_size: ClassVar[str | None] = None
    _percent: ClassVar[int] = 0
    _error_size: ClassVar[str | None] = None
    _error_message: ClassVar[str | None] = None

    @staticmethod
    def get_status(size: str, locale: str) -> WhisperModelStatus:
        """Build current model status for UI and API consumers.

        Args:
            size: Speech model size from provider configuration.
            locale: Interview locale for transcription language label.

        Returns:
            Status snapshot for templates and JSON responses.
        """
        model_size = normalize_speech_model_size(size)
        code = normalize_locale(locale)
        spec = speech_model_spec_for_size(model_size)
        locale_label = SUPPORTED_LOCALES[code]

        if (
            WhisperModelService._error_size == model_size
            and WhisperModelService._error_message is not None
            and WhisperModelService._active_size is None
        ):
            return WhisperModelStatus(
                size=model_size,
                locale=code,
                locale_label=locale_label,
                state="error",
                percent=0,
                message=WhisperModelService._error_message,
                model_display_name=spec.display_name,
            )

        if WhisperModelService._active_size == model_size:
            return WhisperModelStatus(
                size=model_size,
                locale=code,
                locale_label=locale_label,
                state="downloading",
                percent=WhisperModelService._percent,
                message="Downloading speech model…",
                model_display_name=spec.display_name,
            )

        if is_installed(model_size):
            loaded = WhisperRuntime.is_loaded(model_size)
            load_error = WhisperRuntime.load_error()
            if loaded:
                message = f"Speech model ready for dictation in {locale_label}."
            elif load_error:
                message = (
                    "Speech model files are installed but could not be loaded: "
                    f"{load_error}"
                )
            else:
                message = "Speech model installed on disk; loading into memory…"
            return WhisperModelStatus(
                size=model_size,
                locale=code,
                locale_label=locale_label,
                state="ready",
                percent=100,
                message=message,
                model_display_name=spec.display_name,
                loaded_in_memory=loaded,
            )

        return WhisperModelStatus(
            size=model_size,
            locale=code,
            locale_label=locale_label,
            state="missing",
            percent=0,
            message="Speech model is not installed.",
            model_display_name=spec.display_name,
        )

    @staticmethod
    async def start_download(size: str, locale: str) -> WhisperModelStatus:
        """Start a background download when the model is not yet installed.

        Args:
            size: Speech model size from provider configuration.
            locale: Interview locale for status messaging.

        Returns:
            Immediate status after scheduling or skipping work.
        """
        model_size = normalize_speech_model_size(size)
        locale_code = normalize_locale(locale)
        if is_installed(model_size):
            if not WhisperRuntime.is_loaded(model_size):
                await WhisperRuntime.load_size(model_size)
            return WhisperModelService.get_status(model_size, locale_code)

        async with WhisperModelService._download_lock:
            if WhisperModelService._active_size is not None:
                return WhisperModelService.get_status(model_size, locale_code)

            WhisperModelService._active_size = model_size
            WhisperModelService._percent = 0
            WhisperModelService._error_size = None
            WhisperModelService._error_message = None

        asyncio.create_task(WhisperModelService._run_download(model_size))
        return WhisperModelService.get_status(model_size, locale_code)

    @staticmethod
    async def _run_download(size: str) -> None:
        """Execute download and installation, updating shared progress state."""
        try:
            await WhisperModelService._download_and_install(size)
            await WhisperRuntime.load_size(size)
            WhisperModelService._error_size = None
            WhisperModelService._error_message = None
        except Exception as exc:
            logger.exception("Whisper model download failed for size %s", size)
            WhisperModelService._error_size = size
            WhisperModelService._error_message = str(exc)
        finally:
            async with WhisperModelService._download_lock:
                WhisperModelService._active_size = None
                WhisperModelService._percent = 0

    @staticmethod
    async def _download_and_install(size: str) -> None:
        """Download the Hugging Face snapshot into ``data/whisper-models/<size>/``."""
        spec = speech_model_spec_for_size(size)
        target_dir = model_dir(size)
        WHISPER_MODELS_ROOT.mkdir(parents=True, exist_ok=True)
        staging_dir = WHISPER_MODELS_ROOT / f".staging-{size}"

        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            WhisperModelService._percent = 5
            await asyncio.to_thread(
                WhisperModelService._snapshot_download,
                spec,
                staging_dir,
            )
            WhisperModelService._percent = 95
            if not is_valid_model_dir(staging_dir):
                raise ValueError(
                    f"Downloaded snapshot does not contain a valid Whisper model: "
                    f"{spec.hf_repo_id}"
                )

            if target_dir.exists():
                shutil.rmtree(target_dir)
            staging_dir.rename(target_dir)
            WhisperModelService._percent = 100
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

    @staticmethod
    def _snapshot_download(spec: SpeechModelSpec, destination: Path) -> None:
        """Download model files from Hugging Face into ``destination``."""
        snapshot_download(
            repo_id=spec.hf_repo_id,
            local_dir=str(destination),
        )
