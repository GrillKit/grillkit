# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SpeechRuntimeCoordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.speech_transcriber import SpeechTranscriber
from app.platform.domain.config import AppConfig
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator
from app.speech.domain.stt_loader import SttModelLoader
from app.speech.domain.tts_engine import TtsEngine


class MockConfigService:
    """Config service stub returning no saved config."""

    @staticmethod
    def get_config():
        return None


class MockConfigServiceWithModel:
    """Config service stub returning a model + voice enabled config."""

    @staticmethod
    def get_config():
        return AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )


def make_loader(
    *,
    installed: bool = True,
    loaded: bool = False,
    transcriber: SpeechTranscriber | None = None,
) -> MagicMock:
    """Build a spec'd STT loader mock with predictable defaults."""
    loader = MagicMock(spec=SttModelLoader)
    loader.is_installed.return_value = installed
    loader.is_loaded.return_value = loaded
    loader.get.return_value = transcriber
    loader.load_error.return_value = None
    loader.load_size = AsyncMock(return_value=True)
    return loader


def make_engine(
    *,
    installed: bool = True,
    loaded: bool = False,
) -> MagicMock:
    """Build a spec'd TTS engine mock with predictable defaults."""
    engine = MagicMock(spec=TtsEngine)
    engine.is_installed.return_value = installed
    engine.is_loaded.return_value = loaded
    engine.load_error.return_value = None
    engine.load_voice = AsyncMock(return_value=True)
    return engine


def make_coordinator(
    loader: MagicMock,
    engine: MagicMock,
    config_service: type = MockConfigService,
) -> SpeechRuntimeCoordinator:
    """Build a coordinator bound to the given loader, engine and config service."""
    return SpeechRuntimeCoordinator(loader, engine, config_service=config_service)


class TestUnloadAll:
    """Tests for SpeechRuntimeCoordinator.unload_all."""

    def test_unloads_stt_and_tts(self):
        """unload_all unloads the STT loader and the TTS engine."""
        loader = make_loader()
        engine = make_engine()
        coordinator = make_coordinator(loader, engine)

        coordinator.unload_all()

        loader.unload.assert_called_once()
        engine.unload.assert_called_once()


class TestStartup:
    """Tests for SpeechRuntimeCoordinator.startup."""

    @pytest.mark.asyncio
    async def test_startup_loads_both_when_installed(self):
        """startup reads config and loads Whisper and Piper when installed."""
        loader = make_loader(installed=True)
        engine = make_engine(installed=True)
        coordinator = make_coordinator(loader, engine, MockConfigServiceWithModel)

        await coordinator.startup()

        loader.load_size.assert_awaited_once_with("small")
        engine.load_voice.assert_awaited_once_with("en_US-lessac-medium")

    @pytest.mark.asyncio
    async def test_startup_unloads_when_no_config(self):
        """startup unloads both when no config exists."""
        loader = make_loader()
        engine = make_engine()
        coordinator = make_coordinator(loader, engine, MockConfigService)

        await coordinator.startup()

        loader.unload.assert_called_once()
        engine.unload.assert_called_once()


class TestSyncWhisper:
    """Tests for SpeechRuntimeCoordinator.sync_whisper."""

    @pytest.mark.asyncio
    async def test_loads_when_installed(self):
        """sync_whisper loads when the model is installed."""
        loader = make_loader(installed=True)
        coordinator = make_coordinator(loader, make_engine())
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="medium",
        )

        await coordinator.sync_whisper(config)

        loader.load_size.assert_awaited_once_with("medium")

    @pytest.mark.asyncio
    async def test_unloads_when_not_installed(self):
        """sync_whisper unloads when the model is not installed."""
        loader = make_loader(installed=False)
        coordinator = make_coordinator(loader, make_engine())
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="large",
        )

        await coordinator.sync_whisper(config)

        loader.unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unloads_when_no_config(self):
        """sync_whisper unloads when config is None."""
        loader = make_loader()
        coordinator = make_coordinator(loader, make_engine())

        await coordinator.sync_whisper(None)

        loader.unload.assert_called_once()


class TestSyncPiper:
    """Tests for SpeechRuntimeCoordinator.sync_piper."""

    @pytest.mark.asyncio
    async def test_loads_when_enabled_and_installed(self):
        """sync_piper loads a voice when enabled and installed."""
        loader = make_loader()
        engine = make_engine(installed=True)
        coordinator = make_coordinator(loader, engine)
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
        )

        await coordinator.sync_piper(config)

        engine.load_voice.assert_awaited_once_with("en_US-lessac-medium")

    @pytest.mark.asyncio
    async def test_unloads_when_disabled(self):
        """sync_piper unloads when question voice is disabled."""
        loader = make_loader()
        engine = make_engine()
        coordinator = make_coordinator(loader, engine)
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
        )

        await coordinator.sync_piper(config)

        engine.unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unloads_when_not_installed(self):
        """sync_piper unloads when the voice is not on disk."""
        loader = make_loader()
        engine = make_engine(installed=False)
        coordinator = make_coordinator(loader, engine)
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
        )

        await coordinator.sync_piper(config)

        engine.unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_unloads_when_no_config(self):
        """sync_piper unloads when config is None."""
        loader = make_loader()
        engine = make_engine()
        coordinator = make_coordinator(loader, engine)

        await coordinator.sync_piper(None)

        engine.unload.assert_called_once()


class TestReloadAfterConfigSave:
    """Tests for SpeechRuntimeCoordinator.reload_after_config_save."""

    @pytest.mark.asyncio
    async def test_syncs_both_runtimes(self):
        """reload_after_config_save syncs Whisper and Piper."""
        loader = make_loader(installed=True)
        engine = make_engine(installed=True)
        coordinator = make_coordinator(loader, engine)
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
            question_voice_enabled=True,
            tts_voice_id="ru_RU-dmitri-medium",
        )

        await coordinator.reload_after_config_save(config)

        loader.load_size.assert_awaited_once_with("small")
        engine.load_voice.assert_awaited_once_with("ru_RU-dmitri-medium")


class TestPreloadWhisperForActiveInterview:
    """Tests for SpeechRuntimeCoordinator.preload_whisper_for_active_interview."""

    @pytest.mark.asyncio
    async def test_loads_when_interview_active(self):
        """Preloads Whisper when interview is active and model installed."""
        loader = make_loader(installed=True, loaded=False)
        coordinator = make_coordinator(loader, make_engine())
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )

        await coordinator.preload_whisper_for_active_interview(
            config, interview_active=True
        )

        loader.load_size.assert_awaited_once_with("small")

    @pytest.mark.asyncio
    async def test_skips_when_no_config(self):
        """No loading when config is None."""
        loader = make_loader()
        coordinator = make_coordinator(loader, make_engine())

        await coordinator.preload_whisper_for_active_interview(
            None, interview_active=True
        )

        loader.load_size.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_interview_not_active(self):
        """No loading when interview is not active."""
        loader = make_loader()
        coordinator = make_coordinator(loader, make_engine())
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )

        await coordinator.preload_whisper_for_active_interview(
            config, interview_active=False
        )

        loader.load_size.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_already_loaded(self):
        """No loading when the model is already in memory."""
        loader = make_loader(installed=True, loaded=True)
        coordinator = make_coordinator(loader, make_engine())
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )

        await coordinator.preload_whisper_for_active_interview(
            config, interview_active=True
        )

        loader.load_size.assert_not_called()
