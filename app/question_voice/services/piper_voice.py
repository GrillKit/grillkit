# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Piper voice download and on-disk installation."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from huggingface_hub import hf_hub_download

from app.paths import PIPER_VOICES_ROOT
from app.question_voice.domain.voices import (
    PiperVoiceSpec,
    normalize_tts_voice_id,
    voice_spec_for_id,
)
from app.question_voice.services.piper_runtime import PiperRuntime
from app.question_voice.services.piper_storage import (
    is_valid_voice_dir,
    is_voice_installed,
    voice_dir,
)
from app.shared.domain.locales import SUPPORTED_LOCALES, normalize_locale
from app.shared.infrastructure.artifact_download import ArtifactDownloadService
from app.shared.infrastructure.artifact_status import ArtifactStatusBuilder
from app.shared.infrastructure.hf_download_progress import (
    copy_file_with_progress,
    hf_progress_tqdm_factory,
)
from app.shared.infrastructure.model_download import (
    cleanup_staging_dir,
    prepare_staging_dir,
    promote_staging_dir,
)

PIPER_VOICES_REPO_ID = "rhasspy/piper-voices"

PiperVoiceState = Literal["missing", "ready", "downloading", "error"]


@dataclass
class PiperVoiceStatus:
    """Runtime status of a Piper voice for one locale.

    Attributes:
        voice_id: Piper voice identifier from provider configuration.
        locale: Interview locale used for status messaging.
        locale_label: Display name for the locale.
        state: Installation or download state.
        percent: Download progress 0–100 when ``state`` is ``downloading``.
        message: User-facing status or error text.
        voice_display_name: Piper voice label for UI.
        loaded_in_memory: True when the voice is loaded in this process.
    """

    voice_id: str
    locale: str
    locale_label: str
    state: PiperVoiceState
    percent: int
    message: str
    voice_display_name: str
    loaded_in_memory: bool = False


class PiperVoiceService(ArtifactDownloadService):
    """Download and verify offline Piper voices under ``data/piper-voices/``."""

    _download_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _active_key: ClassVar[str | None] = None
    _percent: ClassVar[int] = 0
    _error_key: ClassVar[str | None] = None
    _error_message: ClassVar[str | None] = None

    @staticmethod
    def get_status(voice_id: str, locale: str) -> PiperVoiceStatus:
        """Build current voice status for UI and API consumers.

        Args:
            voice_id: Piper voice id from provider configuration.
            locale: Interview locale for status messaging.

        Returns:
            Status snapshot for templates and JSON responses.
        """
        code = normalize_tts_voice_id(voice_id)
        locale_code = normalize_locale(locale)
        spec = voice_spec_for_id(code)
        locale_label = SUPPORTED_LOCALES[locale_code]

        built = ArtifactStatusBuilder.build(
            key=code,
            service=PiperVoiceService,
            is_installed=lambda: is_voice_installed(code),
            is_loaded=lambda: PiperRuntime.is_loaded(code),
            load_error=PiperRuntime.load_error,
            downloading_message="Downloading question voice…",
            missing_message="Question voice is not installed.",
            ready_loaded_message=f"Question voice ready for {locale_label}.",
            ready_loading_message=(
                "Question voice installed on disk; loading into memory…"
            ),
            ready_load_failed_message=lambda err: (
                f"Question voice files are installed but could not be loaded: {err}"
            ),
        )
        return PiperVoiceStatus(
            voice_id=code,
            locale=locale_code,
            locale_label=locale_label,
            state=built.state,
            percent=built.percent,
            message=built.message,
            voice_display_name=spec.display_name,
            loaded_in_memory=built.loaded_in_memory,
        )

    @staticmethod
    async def start_download(voice_id: str, locale: str) -> PiperVoiceStatus:
        """Start a background download when the voice is not yet installed.

        Args:
            voice_id: Piper voice id from provider configuration.
            locale: Interview locale for status messaging.

        Returns:
            Immediate status after scheduling or skipping work.
        """
        code = normalize_tts_voice_id(voice_id)
        locale_code = normalize_locale(locale)
        if is_voice_installed(code):
            if not PiperRuntime.is_loaded(code):
                await PiperRuntime.load_voice(code)
            return PiperVoiceService.get_status(code, locale_code)

        await PiperVoiceService.schedule_download(
            code,
            PiperVoiceService._run_download,
        )
        return PiperVoiceService.get_status(code, locale_code)

    @staticmethod
    async def _run_download(voice_id: str) -> None:
        """Execute download and installation, updating shared progress state."""
        await PiperVoiceService._download_and_install(voice_id)
        await PiperRuntime.load_voice(voice_id)

    @staticmethod
    async def _download_and_install(voice_id: str) -> None:
        """Download Piper voice files into ``data/piper-voices/<voice_id>/``."""
        spec = voice_spec_for_id(voice_id)
        target_dir = voice_dir(voice_id)
        PIPER_VOICES_ROOT.mkdir(parents=True, exist_ok=True)
        staging_dir = prepare_staging_dir(PIPER_VOICES_ROOT, f".staging-{voice_id}")

        try:
            PiperVoiceService.set_download_percent(1)
            await asyncio.to_thread(
                PiperVoiceService._download_voice_files,
                spec,
                staging_dir,
                PiperVoiceService.set_download_percent,
            )
            PiperVoiceService.set_download_percent(95)
            if not is_valid_voice_dir(staging_dir, voice_id):
                raise ValueError(
                    f"Downloaded files do not contain a valid Piper voice: {voice_id}"
                )

            promote_staging_dir(staging_dir, target_dir)
            PiperVoiceService.set_download_percent(100)
        finally:
            cleanup_staging_dir(staging_dir)

    @staticmethod
    def _download_voice_files(
        spec: PiperVoiceSpec,
        destination: Path,
        set_percent: Callable[[int], None],
    ) -> None:
        """Download ``.onnx`` and ``.onnx.json`` from Hugging Face into ``destination``."""
        filenames = (
            f"{spec.voice_id}.onnx",
            f"{spec.voice_id}.onnx.json",
        )
        file_count = len(filenames)
        span = 90 - 5
        expected_bytes_per_file = max(
            1,
            (spec.approx_download_mb * 1_000_000) // file_count,
        )
        for index, filename in enumerate(filenames):
            percent_min = 5 + (span * index) // file_count
            percent_max = 5 + (span * (index + 1)) // file_count
            file_span = percent_max - percent_min
            download_max = percent_min + (file_span * 8) // 10
            progress_tqdm = hf_progress_tqdm_factory(
                set_percent,
                percent_min=percent_min,
                percent_max=download_max,
                expected_bytes=expected_bytes_per_file,
            )
            repo_path = f"{spec.hf_repo_relpath}/{filename}"
            cached_path = Path(
                hf_hub_download(
                    repo_id=PIPER_VOICES_REPO_ID,
                    filename=repo_path,
                    tqdm_class=progress_tqdm,
                )
            )
            copy_file_with_progress(
                cached_path,
                destination / filename,
                set_percent,
                percent_min=download_max,
                percent_max=percent_max,
            )
