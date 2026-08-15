# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for transcriber resolution."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.domain.config import AppConfig, ConfigService
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator
from app.speech.domain.stt_loader import SttModelLoader
from app.speech.domain.tts_engine import TtsEngine
from app.speech.domain.transcriber_resolver import (
    resolve_speech_transcriber,
    speech_transcriber_unavailable_message,
)


class FakeTranscriber:
    """Fake transcriber implementing SpeechTranscriber protocol."""

    async def transcribe(self, audio, locale):
        return "fake transcript"


class MockConfigService(ConfigService):
    """Config service stub returning no saved config."""

    @staticmethod
    def get_config():
        return None


class MockConfigServiceWithModel(ConfigService):
    """Config service stub returning a model size."""

    @staticmethod
    def get_config():
        return AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="small",
        )


class TestResolveSpeechTranscriber:
    """Tests for resolve_speech_transcriber."""

    def _coordinator(
        self,
        *,
        transcriber=None,
        get_side_effect=None,
        load_error=None,
        config_service: type = MockConfigService,
    ) -> tuple[SpeechRuntimeCoordinator, MagicMock]:
        """Build a coordinator plus its fake STT loader mock."""
        loader = MagicMock(spec=SttModelLoader)
        loader.is_installed.return_value = True
        loader.get.side_effect = get_side_effect or [transcriber]
        loader.load_error.return_value = load_error
        loader.load_size = AsyncMock(return_value=True)
        engine = MagicMock(spec=TtsEngine)
        coordinator = SpeechRuntimeCoordinator(
            loader, engine, config_service=config_service
        )
        return coordinator, loader

    @pytest.mark.asyncio
    async def test_returns_loaded_transcriber_when_present(self):
        """Returns the loaded transcriber from the coordinator."""
        fake = FakeTranscriber()
        coordinator, _ = self._coordinator(transcriber=fake)

        result = await resolve_speech_transcriber(coordinator)

        assert result is fake

    @pytest.mark.asyncio
    async def test_loads_from_runtime_when_empty(self):
        """Falls back to a load when no transcriber is loaded."""
        fake = FakeTranscriber()
        coordinator, loader = self._coordinator(
            get_side_effect=[None, fake],
            config_service=MockConfigServiceWithModel,
        )

        result = await resolve_speech_transcriber(coordinator)

        assert result is fake
        loader.load_size.assert_awaited_once_with("small")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_config(self):
        """Returns None when there is no saved config."""
        coordinator, _ = self._coordinator(get_side_effect=[None, None])

        result = await resolve_speech_transcriber(coordinator)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_load_fails(self):
        """Returns None when a load does not populate a transcriber."""
        coordinator, loader = self._coordinator(
            get_side_effect=[None, None],
            config_service=MockConfigServiceWithModel,
        )

        result = await resolve_speech_transcriber(coordinator)

        assert result is None
        loader.load_size.assert_awaited_once_with("small")

    @pytest.mark.asyncio
    async def test_normalizes_model_size_via_config(self):
        """Config speech_model_size is used for the runtime load."""
        coordinator, loader = self._coordinator(
            get_side_effect=[None, None],
            config_service=MockConfigServiceWithModel,
        )

        await resolve_speech_transcriber(coordinator)

        loader.load_size.assert_awaited_once_with("small")


class TestSpeechTranscriberUnavailableMessage:
    """Tests for speech_transcriber_unavailable_message."""

    def _coordinator(self, *, load_error=None) -> SpeechRuntimeCoordinator:
        loader = MagicMock(spec=SttModelLoader)
        loader.load_error.return_value = load_error
        engine = MagicMock(spec=TtsEngine)
        return SpeechRuntimeCoordinator(
            loader, engine, config_service=MockConfigService
        )

    def test_returns_base_message(self):
        """Returns the standard unavailable message."""
        coordinator = self._coordinator(load_error=None)

        msg = speech_transcriber_unavailable_message(coordinator)

        assert "not loaded" in msg
        assert "Download it in Configuration" in msg

    def test_includes_load_error_when_present(self):
        """Appends the runtime load error when one exists."""
        coordinator = self._coordinator(load_error="Out of memory")

        msg = speech_transcriber_unavailable_message(coordinator)

        assert "Speech model load error: Out of memory" in msg
