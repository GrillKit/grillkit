# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SpeechRuntimeCoordinator."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from app.platform.services.config import AppConfig
from app.platform.services.speech_runtime import SpeechRuntimeCoordinator
from app.platform.services.speech_settings import (
    QuestionVoiceSettings,
    SpeechSettings,
)


@pytest.fixture(autouse=True)
def reset_runtimes():
    """Reset runtime class state before each test."""
    from app.question_voice.services.piper_runtime import PiperRuntime
    from app.speech.services.whisper_runtime import WhisperRuntime

    WhisperRuntime._app = None
    WhisperRuntime._artifact = None
    WhisperRuntime._loaded_key = None
    PiperRuntime._artifact = None
    PiperRuntime._loaded_key = None
    PiperRuntime._load_error = None
    yield
    WhisperRuntime._app = None
    WhisperRuntime._artifact = None
    WhisperRuntime._loaded_key = None
    PiperRuntime._artifact = None
    PiperRuntime._loaded_key = None
    PiperRuntime._load_error = None


class TestUnloadAll:
    """Tests for SpeechRuntimeCoordinator.unload_all."""

    def test_unloads_both_runtimes(self):
        """unload_all calls unload on Whisper and Piper."""
        from app.question_voice.services.piper_runtime import PiperRuntime
        from app.speech.services.whisper_runtime import WhisperRuntime

        with (
            patch.object(WhisperRuntime, "unload") as mock_whisper_unload,
            patch.object(PiperRuntime, "unload") as mock_piper_unload,
        ):
            SpeechRuntimeCoordinator.unload_all()

        mock_whisper_unload.assert_called_once()
        mock_piper_unload.assert_called_once()


class TestStartup:
    """Tests for SpeechRuntimeCoordinator.startup."""

    @pytest.mark.asyncio
    async def test_startup_binds_app_and_loads_both(self):
        """startup binds app, loads Whisper and Piper when installed."""
        from app.question_voice.services.piper_runtime import PiperRuntime
        from app.speech.services.whisper_runtime import WhisperRuntime

        app = FastAPI()
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )

        with (
            patch.object(WhisperRuntime, "bind_app") as mock_bind,
            patch(
                "app.platform.services.speech_runtime.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.platform.services.speech_runtime.is_installed",
                return_value=True,
            ),
            patch(
                "app.platform.services.speech_runtime.is_voice_installed",
                return_value=True,
            ),
            patch.object(
                WhisperRuntime,
                "load_size",
                return_value=True,
            ) as mock_whisper_load,
            patch.object(
                PiperRuntime,
                "load_voice",
                return_value=True,
            ) as mock_piper_load,
        ):
            await SpeechRuntimeCoordinator.startup(app)

        mock_bind.assert_called_once_with(app)
        mock_whisper_load.assert_awaited_once_with("small")
        mock_piper_load.assert_awaited_once_with("en_US-lessac-medium")

    @pytest.mark.asyncio
    async def test_startup_skips_when_no_config(self):
        """startup unloads both when no config exists."""
        from app.question_voice.services.piper_runtime import PiperRuntime
        from app.speech.services.whisper_runtime import WhisperRuntime

        app = FastAPI()

        with (
            patch.object(WhisperRuntime, "bind_app") as mock_bind,
            patch(
                "app.platform.services.speech_runtime.ConfigService.get_config",
                return_value=None,
            ),
            patch.object(WhisperRuntime, "unload") as mock_whisper_unload,
            patch.object(PiperRuntime, "unload") as mock_piper_unload,
        ):
            await SpeechRuntimeCoordinator.startup(app)

        mock_bind.assert_called_once_with(app)
        mock_whisper_unload.assert_called_once()
        mock_piper_unload.assert_called_once()


class TestSyncWhisper:
    """Tests for SpeechRuntimeCoordinator.sync_whisper."""

    @pytest.mark.asyncio
    async def test_loads_when_installed(self):
        """sync_whisper loads when model is installed."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="medium",
        )

        with (
            patch(
                "app.platform.services.speech_runtime.is_installed",
                return_value=True,
            ),
            patch.object(
                WhisperRuntime,
                "load_size",
                return_value=True,
            ) as mock_load,
        ):
            await SpeechRuntimeCoordinator.sync_whisper(config)

        mock_load.assert_awaited_once_with("medium")

    @pytest.mark.asyncio
    async def test_unloads_when_not_installed(self):
        """sync_whisper unloads when model is not installed."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="large",
        )

        with (
            patch(
                "app.platform.services.speech_runtime.is_installed",
                return_value=False,
            ),
            patch.object(WhisperRuntime, "unload") as mock_unload,
        ):
            await SpeechRuntimeCoordinator.sync_whisper(config)

        mock_unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unloads_when_no_config(self):
        """sync_whisper unloads when config is None."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        with patch.object(WhisperRuntime, "unload") as mock_unload:
            await SpeechRuntimeCoordinator.sync_whisper(None)

        mock_unload.assert_called_once()


class TestSyncPiper:
    """Tests for SpeechRuntimeCoordinator.sync_piper."""

    @pytest.mark.asyncio
    async def test_loads_when_enabled_and_installed(self):
        """sync_piper loads voice when enabled and installed."""
        from app.question_voice.services.piper_runtime import PiperRuntime

        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
        )

        with (
            patch(
                "app.platform.services.speech_runtime.is_voice_installed",
                return_value=True,
            ),
            patch.object(
                PiperRuntime,
                "load_voice",
                return_value=True,
            ) as mock_load,
        ):
            await SpeechRuntimeCoordinator.sync_piper(config)

        mock_load.assert_awaited_once_with("en_US-lessac-medium")

    @pytest.mark.asyncio
    async def test_unloads_when_disabled(self):
        """sync_piper unloads when question voice is disabled."""
        from app.question_voice.services.piper_runtime import PiperRuntime

        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
        )

        with patch.object(PiperRuntime, "unload") as mock_unload:
            await SpeechRuntimeCoordinator.sync_piper(config)

        mock_unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unloads_when_not_installed(self):
        """sync_piper unloads when voice is not on disk."""
        from app.question_voice.services.piper_runtime import PiperRuntime

        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
        )

        with (
            patch(
                "app.platform.services.speech_runtime.is_voice_installed",
                return_value=False,
            ),
            patch.object(PiperRuntime, "unload") as mock_unload,
        ):
            await SpeechRuntimeCoordinator.sync_piper(config)

        mock_unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unloads_when_no_config(self):
        """sync_piper unloads when config is None."""
        from app.question_voice.services.piper_runtime import PiperRuntime

        with patch.object(PiperRuntime, "unload") as mock_unload:
            await SpeechRuntimeCoordinator.sync_piper(None)

        mock_unload.assert_called_once()


class TestReloadAfterConfigSave:
    """Tests for SpeechRuntimeCoordinator.reload_after_config_save."""

    @pytest.mark.asyncio
    async def test_reloads_whisper_and_piper(self):
        """reload_after_config_save re-runs sync for both runtimes."""
        from app.question_voice.services.piper_runtime import PiperRuntime
        from app.speech.services.whisper_runtime import WhisperRuntime

        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
            question_voice_enabled=True,
            tts_voice_id="ru_RU-dmitri-medium",
        )

        with (
            patch(
                "app.platform.services.speech_runtime.is_installed",
                return_value=True,
            ),
            patch(
                "app.platform.services.speech_runtime.is_voice_installed",
                return_value=True,
            ),
            patch.object(
                WhisperRuntime,
                "load_size",
                return_value=True,
            ) as mock_whisper_load,
            patch.object(
                PiperRuntime,
                "load_voice",
                return_value=True,
            ) as mock_piper_load,
        ):
            await SpeechRuntimeCoordinator.reload_after_config_save(config)

        mock_whisper_load.assert_awaited_once_with("small")
        mock_piper_load.assert_awaited_once_with("ru_RU-dmitri-medium")


class TestPreloadWhisperForActiveInterview:
    """Tests for SpeechRuntimeCoordinator.preload_whisper_for_active_interview."""

    @pytest.mark.asyncio
    async def test_loads_when_interview_active(self):
        """Preloads Whisper when interview is active and model installed."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        app = FastAPI()
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )

        with (
            patch.object(WhisperRuntime, "bind_app") as mock_bind,
            patch(
                "app.platform.services.speech_runtime.is_installed",
                return_value=True,
            ),
            patch.object(
                WhisperRuntime,
                "is_loaded",
                return_value=False,
            ),
            patch.object(
                WhisperRuntime,
                "load_size",
                return_value=True,
            ) as mock_load,
        ):
            await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
                app, config, interview_active=True
            )

        mock_bind.assert_called_once_with(app)
        mock_load.assert_awaited_once_with("small")

    @pytest.mark.asyncio
    async def test_skips_when_no_config(self):
        """No loading when config is None."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        app = FastAPI()

        with (
            patch.object(WhisperRuntime, "bind_app") as mock_bind,
            patch.object(WhisperRuntime, "load_size") as mock_load,
        ):
            await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
                app, None, interview_active=True
            )

        mock_bind.assert_called_once_with(app)
        mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_interview_not_active(self):
        """No loading when interview is not active."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        app = FastAPI()
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )

        with (
            patch.object(WhisperRuntime, "bind_app") as mock_bind,
            patch.object(WhisperRuntime, "load_size") as mock_load,
        ):
            await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
                app, config, interview_active=False
            )

        mock_bind.assert_called_once_with(app)
        mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_already_loaded(self):
        """No loading when model is already in memory."""
        from app.speech.services.whisper_runtime import WhisperRuntime

        app = FastAPI()
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )

        with (
            patch.object(WhisperRuntime, "bind_app") as mock_bind,
            patch(
                "app.platform.services.speech_runtime.is_installed",
                return_value=True,
            ),
            patch.object(
                WhisperRuntime,
                "is_loaded",
                return_value=True,
            ),
            patch.object(WhisperRuntime, "load_size") as mock_load,
        ):
            await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
                app, config, interview_active=True
            )

        mock_bind.assert_called_once_with(app)
        mock_load.assert_not_called()
