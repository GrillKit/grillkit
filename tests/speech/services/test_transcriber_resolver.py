# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for transcriber resolution."""

from unittest.mock import patch

import pytest
from starlette.applications import Starlette

from app.speech.services.transcriber_resolver import (
    resolve_speech_transcriber,
    speech_transcriber_unavailable_message,
)


class FakeTranscriber:
    """Fake transcriber implementing SpeechTranscriber protocol."""

    async def transcribe(self, audio, locale):
        return "fake transcript"


class TestResolveSpeechTranscriber:
    """Tests for resolve_speech_transcriber."""

    @pytest.fixture
    def app(self):
        """Create a Starlette app with clean state."""
        return Starlette()

    @pytest.fixture
    def mock_config_service(self):
        """Return a mock ConfigService class with no config."""

        class MockConfigService:
            @staticmethod
            def get_config():
                return None

        return MockConfigService

    @pytest.mark.asyncio
    async def test_returns_app_state_transcriber_when_present(
        self, app, mock_config_service
    ):
        """Returns speech_transcriber from app.state when available."""
        fake = FakeTranscriber()
        app.state.speech_transcriber = fake

        result = await resolve_speech_transcriber(app, mock_config_service)

        assert result is fake

    @pytest.mark.asyncio
    async def test_loads_from_runtime_when_app_state_none(
        self, app, mock_config_service
    ):
        """Falls back to WhisperRuntime.load_size when app.state is empty."""
        fake = FakeTranscriber()
        app.state.speech_transcriber = None

        class ConfigWithModel:
            speech_model_size = "small"

        class MockConfigServiceWithModel:
            @staticmethod
            def get_config():
                return ConfigWithModel()

        with (
            patch(
                "app.speech.services.transcriber_resolver.is_installed",
                return_value=True,
            ),
            patch(
                "app.speech.services.transcriber_resolver.WhisperRuntime.load_size"
            ) as mock_load,
        ):

            async def _load_and_set(size):
                app.state.speech_transcriber = fake
                return True

            mock_load.side_effect = _load_and_set
            result = await resolve_speech_transcriber(app, MockConfigServiceWithModel)

        assert result is fake
        mock_load.assert_called_once_with("small")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_installed(self, app, mock_config_service):
        """Returns None when model is not installed."""
        app.state.speech_transcriber = None

        class ConfigWithModel:
            speech_model_size = "small"

        class MockConfigServiceWithModel:
            @staticmethod
            def get_config():
                return ConfigWithModel()

        with patch(
            "app.speech.services.transcriber_resolver.is_installed",
            return_value=False,
        ):
            result = await resolve_speech_transcriber(app, MockConfigServiceWithModel)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_config(self, app, mock_config_service):
        """Returns None when there is no saved config."""
        app.state.speech_transcriber = None

        result = await resolve_speech_transcriber(app, mock_config_service)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_load_fails(self, app, mock_config_service):
        """Returns None when runtime load fails and app.state stays empty."""
        app.state.speech_transcriber = None

        class ConfigWithModel:
            speech_model_size = "medium"

        class MockConfigServiceWithModel:
            @staticmethod
            def get_config():
                return ConfigWithModel()

        with (
            patch(
                "app.speech.services.transcriber_resolver.is_installed",
                return_value=True,
            ),
            patch(
                "app.speech.services.transcriber_resolver.WhisperRuntime.load_size",
                return_value=False,
            ) as mock_load,
        ):
            result = await resolve_speech_transcriber(app, MockConfigServiceWithModel)

        assert result is None
        mock_load.assert_called_once_with("medium")

    @pytest.mark.asyncio
    async def test_normalizes_model_size_via_config(self, app, mock_config_service):
        """Config speech_model_size is used for runtime lookup."""
        app.state.speech_transcriber = None

        class ConfigWithModel:
            speech_model_size = "large"

        class MockConfigServiceWithModel:
            @staticmethod
            def get_config():
                return ConfigWithModel()

        with (
            patch(
                "app.speech.services.transcriber_resolver.is_installed",
                return_value=True,
            ),
            patch(
                "app.speech.services.transcriber_resolver.WhisperRuntime.load_size",
                return_value=False,
            ) as mock_load,
        ):
            await resolve_speech_transcriber(app, MockConfigServiceWithModel)

        mock_load.assert_called_once_with("large")


class TestSpeechTranscriberUnavailableMessage:
    """Tests for speech_transcriber_unavailable_message."""

    def test_returns_base_message(self):
        """Returns the standard unavailable message."""
        with patch(
            "app.speech.services.transcriber_resolver.WhisperRuntime.load_error",
            return_value=None,
        ):
            msg = speech_transcriber_unavailable_message()

        assert "not loaded" in msg
        assert "Download it in Configuration" in msg

    def test_includes_load_error_when_present(self):
        """Appends runtime load error when one exists."""
        with patch(
            "app.speech.services.transcriber_resolver.WhisperRuntime.load_error",
            return_value="Out of memory",
        ):
            msg = speech_transcriber_unavailable_message()

        assert "Speech model load error: Out of memory" in msg
