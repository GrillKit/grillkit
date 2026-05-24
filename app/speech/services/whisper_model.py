# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Whisper speech model download and on-disk installation."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from huggingface_hub import snapshot_download

from app.paths import WHISPER_MODELS_ROOT
from app.shared.domain.locales import SUPPORTED_LOCALES, normalize_locale
from app.shared.infrastructure.artifact_download import ArtifactDownloadService
from app.shared.infrastructure.artifact_status import ArtifactStatusBuilder
from app.shared.infrastructure.hf_download_progress import hf_progress_tqdm_factory
from app.shared.infrastructure.model_download import (
    cleanup_staging_dir,
    prepare_staging_dir,
    promote_staging_dir,
)
from app.speech.domain.models import (
    SpeechModelSpec,
    normalize_speech_model_size,
    speech_model_spec_for_size,
)
from app.speech.services.whisper_runtime import WhisperRuntime
from app.speech.services.whisper_storage import (
    is_installed,
    is_valid_model_dir,
    model_dir,
)

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


class WhisperModelService(ArtifactDownloadService):
    """Download and verify offline Whisper models under ``data/whisper-models/``."""

    _download_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _active_key: ClassVar[str | None] = None
    _percent: ClassVar[int] = 0
    _error_key: ClassVar[str | None] = None
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

        built = ArtifactStatusBuilder.build(
            key=model_size,
            service=WhisperModelService,
            is_installed=lambda: is_installed(model_size),
            is_loaded=lambda: WhisperRuntime.is_loaded(model_size),
            load_error=WhisperRuntime.load_error,
            downloading_message="Downloading speech model…",
            missing_message="Speech model is not installed.",
            ready_loaded_message=f"Speech model ready for dictation in {locale_label}.",
            ready_loading_message="Speech model installed on disk; loading into memory…",
            ready_load_failed_message=lambda err: (
                f"Speech model files are installed but could not be loaded: {err}"
            ),
        )
        return WhisperModelStatus(
            size=model_size,
            locale=code,
            locale_label=locale_label,
            state=built.state,
            percent=built.percent,
            message=built.message,
            model_display_name=spec.display_name,
            loaded_in_memory=built.loaded_in_memory,
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

        await WhisperModelService.schedule_download(
            model_size,
            WhisperModelService._run_download,
        )
        return WhisperModelService.get_status(model_size, locale_code)

    @staticmethod
    async def _run_download(size: str) -> None:
        """Execute download and installation, updating shared progress state."""
        await WhisperModelService._download_and_install(size)
        await WhisperRuntime.load_size(size)

    @staticmethod
    async def _download_and_install(size: str) -> None:
        """Download the Hugging Face snapshot into ``data/whisper-models/<size>/``."""
        spec = speech_model_spec_for_size(size)
        target_dir = model_dir(size)
        WHISPER_MODELS_ROOT.mkdir(parents=True, exist_ok=True)
        staging_dir = prepare_staging_dir(WHISPER_MODELS_ROOT, f".staging-{size}")

        try:
            WhisperModelService.set_download_percent(1)
            await asyncio.to_thread(
                WhisperModelService._snapshot_download,
                spec,
                staging_dir,
                WhisperModelService.set_download_percent,
            )
            WhisperModelService.set_download_percent(95)
            if not is_valid_model_dir(staging_dir):
                raise ValueError(
                    f"Downloaded snapshot does not contain a valid Whisper model: "
                    f"{spec.hf_repo_id}"
                )

            promote_staging_dir(staging_dir, target_dir)
            WhisperModelService.set_download_percent(100)
        finally:
            cleanup_staging_dir(staging_dir)

    @staticmethod
    def _snapshot_download(
        spec: SpeechModelSpec,
        destination: Path,
        set_percent: Callable[[int], None],
    ) -> None:
        """Download model files from Hugging Face into ``destination``."""
        expected_bytes = spec.approx_download_mb * 1_000_000
        progress_tqdm = hf_progress_tqdm_factory(
            set_percent,
            percent_min=5,
            percent_max=90,
            expected_bytes=expected_bytes,
        )
        snapshot_download(
            repo_id=spec.hf_repo_id,
            local_dir=str(destination),
            tqdm_class=progress_tqdm,
        )
