# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coordinate Whisper and Piper in-process runtimes across app lifecycle."""

from fastapi import FastAPI

from app.platform.services.config import ConfigService, ProviderConfig
from app.platform.services.speech_settings import (
    question_voice_settings_from_config,
    speech_settings_from_config,
)
from app.question_voice.services.piper_runtime import PiperRuntime
from app.question_voice.services.piper_storage import is_voice_installed
from app.speech.services.whisper_runtime import WhisperRuntime
from app.speech.services.whisper_storage import is_installed


class SpeechRuntimeCoordinator:
    """Load or unload speech artifacts on startup, config save, and interview pages."""

    @staticmethod
    def unload_all() -> None:
        """Unload in-process Whisper and Piper models synchronously."""
        WhisperRuntime.unload()
        PiperRuntime.unload()

    @staticmethod
    async def startup(app: FastAPI) -> None:
        """Bind Whisper to the app and load configured artifacts when installed.

        Args:
            app: FastAPI application instance.
        """
        WhisperRuntime.bind_app(app)
        config = ConfigService.get_config()
        await SpeechRuntimeCoordinator.sync_whisper(config)
        await SpeechRuntimeCoordinator.sync_piper(config)

    @staticmethod
    async def shutdown() -> None:
        """Unload in-process Whisper and Piper models."""
        SpeechRuntimeCoordinator.unload_all()

    @staticmethod
    async def sync_whisper(config: ProviderConfig | None) -> None:
        """Load or unload Whisper based on configuration and on-disk install state.

        Args:
            config: Saved provider configuration, if any.
        """
        if config is None:
            WhisperRuntime.unload()
            return
        settings = speech_settings_from_config(config)
        if is_installed(settings.speech_model_size):
            await WhisperRuntime.load_size(settings.speech_model_size)
        else:
            WhisperRuntime.unload()

    @staticmethod
    async def sync_piper(config: ProviderConfig | None) -> None:
        """Load or unload Piper based on configuration and on-disk install state.

        Args:
            config: Saved provider configuration, if any.
        """
        if config is None:
            PiperRuntime.unload()
            return
        settings = question_voice_settings_from_config(config)
        if settings.enabled and is_voice_installed(settings.voice_id):
            await PiperRuntime.load_voice(settings.voice_id)
        else:
            PiperRuntime.unload()

    @staticmethod
    async def reload_after_config_save(config: ProviderConfig) -> None:
        """Reload speech runtimes after configuration is persisted.

        Args:
            config: Configuration that was just saved.
        """
        await SpeechRuntimeCoordinator.sync_whisper(config)
        await SpeechRuntimeCoordinator.sync_piper(config)

    @staticmethod
    async def preload_whisper_for_active_interview(
        app: FastAPI,
        config: ProviderConfig | None,
        *,
        interview_active: bool,
    ) -> None:
        """Ensure Whisper is bound and loaded when an interview session is active.

        Args:
            app: FastAPI application instance.
            config: Saved provider configuration.
            interview_active: Whether the interview session is still active.
        """
        WhisperRuntime.bind_app(app)
        if config is None or not interview_active:
            return
        settings = speech_settings_from_config(config)
        if is_installed(settings.speech_model_size) and not WhisperRuntime.is_loaded(
            settings.speech_model_size
        ):
            await WhisperRuntime.load_size(settings.speech_model_size)
