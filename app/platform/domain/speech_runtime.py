# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coordinate in-process speech runtimes (STT and TTS) across the app lifecycle."""

from app.ai.speech_transcriber import SpeechTranscriber
from app.platform.domain.config import AppConfig, ConfigService
from app.platform.domain.speech_settings import (
    question_voice_settings_from_config,
    speech_settings_from_config,
)
from app.speech.domain.stt_loader import SttModelLoader
from app.speech.domain.tts_engine import TtsEngine


class SpeechRuntimeCoordinator:
    """Single owner of in-process speech artifacts.

    Created during the FastAPI lifespan and exposed through ``app.state`` /
    dependency injection. All read/write access to the loaded speech models flows
    through this coordinator so the concrete STT/TTS backends can be swapped
    without touching the rest of the application.
    """

    def __init__(
        self,
        stt_loader: SttModelLoader,
        tts_engine: TtsEngine,
        config_service: type[ConfigService] = ConfigService,
    ) -> None:
        """Initialize the coordinator with STT and TTS backends.

        Args:
            stt_loader: Backend that loads a :class:`SpeechTranscriber` into memory.
            tts_engine: Backend that holds a voice and synthesizes WAV bytes.
            config_service: Provider configuration service class.
        """
        self._stt = stt_loader
        self._tts = tts_engine
        self._config_service = config_service

    @property
    def config_service(self) -> type[ConfigService]:
        """Return the configuration service class bound to this coordinator."""
        return self._config_service

    @property
    def tts(self) -> TtsEngine:
        """Return the TTS engine owned by this coordinator."""
        return self._tts

    def unload_all(self) -> None:
        """Unload any in-memory Whisper and Piper models."""
        self._stt.unload()
        self._tts.unload()

    async def startup(self) -> None:
        """Load configured speech artifacts when installed."""
        _ = await self.sync(self._config_service.get_config())

    async def shutdown(self) -> None:
        """Unload all in-memory speech artifacts."""
        self.unload_all()

    async def sync(self, config: AppConfig | None) -> list[str]:
        """Align both speech runtimes with the given configuration.

        Args:
            config: Saved provider configuration, if any.

        Returns:
            Human-readable load errors for STT/TTS that failed to load, if any.
        """
        errors: list[str] = []
        if stt_error := await self.sync_whisper(config):
            errors.append(stt_error)
        if tts_error := await self.sync_piper(config):
            errors.append(tts_error)
        return errors

    async def reload_after_config_save(self, config: AppConfig) -> list[str]:
        """Reload speech runtimes after configuration is persisted.

        Args:
            config: Configuration that was just saved.

        Returns:
            Human-readable load errors for STT/TTS that failed to load, if any.
        """
        return await self.sync(config)

    async def sync_whisper(self, config: AppConfig | None) -> str | None:
        """Load or unload Whisper based on configuration and on-disk install state.

        Args:
            config: Saved provider configuration, if any.

        Returns:
            A load error message when Whisper failed to load, otherwise ``None``.
        """
        if config is None:
            self._stt.unload()
            return None
        settings = speech_settings_from_config(config)
        if self._stt.is_installed(settings.speech_model_size):
            _ = await self._stt.load_size(settings.speech_model_size)
        else:
            self._stt.unload()
        return self._stt.load_error()

    async def sync_piper(self, config: AppConfig | None) -> str | None:
        """Load or unload Piper based on configuration and on-disk install state.

        Args:
            config: Saved provider configuration, if any.

        Returns:
            A load error message when Piper failed to load, otherwise ``None``.
        """
        if config is None:
            self._tts.unload()
            return None
        settings = question_voice_settings_from_config(config)
        if settings.enabled and self._tts.is_installed(settings.voice_id):
            _ = await self._tts.load_voice(settings.voice_id)
        else:
            self._tts.unload()
        return self._tts.load_error()

    async def preload_whisper_for_active_interview(
        self,
        config: AppConfig | None,
        *,
        interview_active: bool,
    ) -> None:
        """Ensure Whisper is loaded when an interview session is active.

        Args:
            config: Saved provider configuration.
            interview_active: Whether the interview session is still active.
        """
        if config is None or not interview_active:
            return
        settings = speech_settings_from_config(config)
        if self._stt.is_installed(
            settings.speech_model_size
        ) and not self._stt.is_loaded(settings.speech_model_size):
            _ = await self._stt.load_size(settings.speech_model_size)

    def get_transcriber(self) -> SpeechTranscriber | None:
        """Return the currently loaded speech transcriber, if any."""
        return self._stt.get()

    def load_error(self) -> str | None:
        """Return the last STT load error message, if any."""
        return self._stt.load_error()

    def is_loaded(self, size: str) -> bool:
        """Return whether the STT model for ``size`` is loaded in memory."""
        return self._stt.is_loaded(size)
