# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for PiperRuntime in-process voice loading and synthesis."""

from unittest.mock import MagicMock, patch

import pytest

from app.question_voice.services.piper_runtime import PiperRuntime


class TestPiperRuntimeLoad:
    """Tests for PiperRuntime.load_voice."""

    @pytest.fixture(autouse=True)
    def reset_runtime(self):
        """Reset the runtime class state before each test."""
        PiperRuntime._artifact = None
        PiperRuntime._loaded_key = None
        PiperRuntime._load_error = None
        yield
        PiperRuntime._artifact = None
        PiperRuntime._loaded_key = None
        PiperRuntime._load_error = None

    @pytest.mark.asyncio
    async def test_load_voice_returns_true_when_installed(self):
        """load_voice returns True when voice is installed and loads."""
        mock_voice = MagicMock()
        with (
            patch.object(PiperRuntime, "is_installed", return_value=True),
            patch.object(
                PiperRuntime, "load_sync", return_value=mock_voice
            ) as mock_load_sync,
        ):
            result = await PiperRuntime.load_voice("en_US-lessac-medium")
        assert result is True
        assert PiperRuntime.is_loaded("en_US-lessac-medium")
        mock_load_sync.assert_called_once_with("en_US-lessac-medium")

    @pytest.mark.asyncio
    async def test_load_voice_returns_false_when_not_installed(self):
        """load_voice returns False when voice is not on disk."""
        with patch.object(PiperRuntime, "is_installed", return_value=False):
            result = await PiperRuntime.load_voice("en_US-lessac-medium")
        assert result is False
        assert not PiperRuntime.is_loaded("en_US-lessac-medium")

    @pytest.mark.asyncio
    async def test_load_voice_logs_success(self):
        """Successful load logs the voice directory."""
        mock_voice = MagicMock()
        with (
            patch.object(PiperRuntime, "is_installed", return_value=True),
            patch.object(PiperRuntime, "load_sync", return_value=mock_voice),
            patch("app.question_voice.services.piper_runtime.logger") as mock_logger,
        ):
            await PiperRuntime.load_voice("en_US-lessac-medium")
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        assert "en_US-lessac-medium" in args

    @pytest.mark.asyncio
    async def test_load_voice_handles_error(self):
        """load_voice records error and returns False on exception."""
        with (
            patch.object(PiperRuntime, "is_installed", return_value=True),
            patch.object(
                PiperRuntime, "load_sync", side_effect=RuntimeError("corrupt model")
            ),
            patch("app.shared.infrastructure.in_process_runtime.logger") as mock_logger,
        ):
            result = await PiperRuntime.load_voice("en_US-lessac-medium")
        assert result is False
        assert PiperRuntime.load_error() == "corrupt model"
        mock_logger.exception.assert_called_once()


class TestPiperRuntimeSynthesize:
    """Tests for PiperRuntime.synthesize_wav_bytes."""

    @pytest.fixture(autouse=True)
    def reset_runtime(self):
        """Reset the runtime class state before each test."""
        PiperRuntime._artifact = None
        PiperRuntime._loaded_key = None
        PiperRuntime._load_error = None
        yield
        PiperRuntime._artifact = None
        PiperRuntime._loaded_key = None
        PiperRuntime._load_error = None

    def test_synthesize_wav_bytes_sync_raises_when_no_voice_loaded(self):
        """synthesize_wav_bytes_sync raises RuntimeError when voice not loaded."""
        with pytest.raises(RuntimeError, match="Piper voice is not loaded"):
            PiperRuntime.synthesize_wav_bytes_sync("Hello world")

    def test_synthesize_wav_bytes_sync_returns_bytes(self):
        """synthesize_wav_bytes_sync returns raw WAV bytes."""
        mock_voice = MagicMock()
        mock_buffer = MagicMock()
        mock_buffer.getvalue.return_value = b"RIFFwavdata"

        PiperRuntime._artifact = mock_voice
        PiperRuntime._loaded_key = "en_US-lessac-medium"

        mock_wave_file = MagicMock()
        with (
            patch("io.BytesIO", return_value=mock_buffer),
            patch("wave.open", return_value=mock_wave_file),
        ):
            result = PiperRuntime.synthesize_wav_bytes_sync("Hello world")

        assert result == b"RIFFwavdata"
        mock_voice.synthesize_wav.assert_called_once_with(
            "Hello world", mock_wave_file.__enter__()
        )

    @pytest.mark.asyncio
    async def test_synthesize_wav_bytes_delegates_to_sync(self):
        """synthesize_wav_bytes runs sync version in a worker thread."""
        with patch.object(
            PiperRuntime,
            "synthesize_wav_bytes_sync",
            return_value=b"RIFFasyncwav",
        ) as mock_sync:
            result = await PiperRuntime.synthesize_wav_bytes("Hello world")
        assert result == b"RIFFasyncwav"
        mock_sync.assert_called_once_with("Hello world")


class TestPiperRuntimeNormalizeAndInstalled:
    """Tests for normalize_key and is_installed."""

    def test_normalize_key_returns_normalized_voice_id(self):
        """normalize_key delegates to normalize_tts_voice_id."""
        assert (
            PiperRuntime.normalize_key("en_US-lessac-medium") == "en_US-lessac-medium"
        )

    def test_is_installed_delegates_to_piper_storage(self):
        """is_installed checks voice installation via storage module."""
        with patch(
            "app.question_voice.services.piper_runtime.is_voice_installed",
            return_value=True,
        ) as mock_is_installed:
            result = PiperRuntime.is_installed("en_US-lessac-medium")
        assert result is True
        mock_is_installed.assert_called_once_with("en_US-lessac-medium")

    def test_is_installed_returns_false_for_uninstalled(self):
        """is_installed returns False when voice is not on disk."""
        with patch(
            "app.question_voice.services.piper_runtime.is_voice_installed",
            return_value=False,
        ):
            result = PiperRuntime.is_installed("ru_RU-dmitri-medium")
        assert result is False

    def test_load_sync_builds_paths_and_calls_piper_voice(self):
        """load_sync constructs paths and delegates to PiperVoice.load."""
        mock_piper_voice_class = MagicMock()
        mock_voice_instance = MagicMock()
        mock_piper_voice_class.load.return_value = mock_voice_instance

        mock_dir = MagicMock()
        mock_model_path = MagicMock()
        mock_config_path = MagicMock()
        mock_dir.__truediv__ = MagicMock(
            side_effect=[mock_model_path, mock_config_path]
        )

        with (
            patch(
                "app.question_voice.services.piper_runtime.voice_dir",
                return_value=mock_dir,
            ),
            patch.dict(
                "sys.modules",
                {"piper": MagicMock(PiperVoice=mock_piper_voice_class)},
            ),
        ):
            result = PiperRuntime.load_sync("en_US-lessac-medium")

        assert result == mock_voice_instance
        mock_piper_voice_class.load.assert_called_once_with(
            mock_model_path, config_path=mock_config_path
        )
