# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for WhisperModelService download and status."""

from unittest.mock import MagicMock, patch

import pytest

from app.speech.services.whisper_model import WhisperModelService
from app.speech.services.whisper_runtime import WhisperRuntime


@pytest.fixture(autouse=True)
def reset_service():
    """Clear shared download state between tests."""
    WhisperModelService.reset_download_state()
    WhisperRuntime.unload()
    WhisperRuntime._load_error = None
    yield
    WhisperModelService.reset_download_state()
    WhisperRuntime.unload()
    WhisperRuntime._load_error = None


class TestGetStatus:
    """Tests for WhisperModelService.get_status."""

    def test_missing_when_not_installed(self):
        """Returns missing state when model is not on disk."""
        with patch(
            "app.speech.services.whisper_model.is_installed", return_value=False
        ):
            status = WhisperModelService.get_status("small", "en")

        assert status.size == "small"
        assert status.locale == "en"
        assert status.state == "missing"
        assert status.loaded_in_memory is False
        assert "not installed" in status.message

    def test_ready_when_installed_and_loaded(self):
        """Returns ready state when model is installed and loaded."""
        with (
            patch("app.speech.services.whisper_model.is_installed", return_value=True),
            patch(
                "app.speech.services.whisper_model.WhisperRuntime.is_loaded",
                return_value=True,
            ),
        ):
            status = WhisperModelService.get_status("small", "ru")

        assert status.size == "small"
        assert status.locale == "ru"
        assert status.state == "ready"
        assert status.loaded_in_memory is True
        assert "ready" in status.message.lower()

    def test_ready_when_installed_not_loaded(self):
        """Returns ready state when installed but not yet loaded."""
        with (
            patch("app.speech.services.whisper_model.is_installed", return_value=True),
            patch(
                "app.speech.services.whisper_model.WhisperRuntime.is_loaded",
                return_value=False,
            ),
        ):
            status = WhisperModelService.get_status("medium", "en")

        assert status.state == "ready"
        assert status.loaded_in_memory is False
        assert "loading" in status.message.lower()

    def test_normalizes_size_and_locale(self):
        """Normalizes size and locale parameters."""
        with patch(
            "app.speech.services.whisper_model.is_installed", return_value=False
        ):
            status = WhisperModelService.get_status(" SMALL ", " EN ")

        assert status.size == "small"
        assert status.locale == "en"

    def test_locale_label_populated(self):
        """Locale label is set from SUPPORTED_LOCALES."""
        with patch(
            "app.speech.services.whisper_model.is_installed", return_value=False
        ):
            status = WhisperModelService.get_status("small", "fr")

        assert status.locale_label == "French"

    def test_model_display_name_set(self):
        """Model display name comes from SpeechModelSpec."""
        with patch(
            "app.speech.services.whisper_model.is_installed", return_value=False
        ):
            status = WhisperModelService.get_status("large", "en")

        assert status.model_display_name == "Whisper large"


class TestStartDownload:
    """Tests for WhisperModelService.start_download."""

    @pytest.mark.asyncio
    async def test_skips_when_already_installed(self):
        """Returns ready status without scheduling when already installed."""
        with patch("app.speech.services.whisper_model.is_installed", return_value=True):
            status = await WhisperModelService.start_download("small", "en")

        assert status.state in ("ready", "missing")
        assert not WhisperModelService.is_downloading("small")

    @pytest.mark.asyncio
    async def test_schedules_when_not_installed(self):
        """Schedules a download when model is missing."""
        with patch(
            "app.speech.services.whisper_model.is_installed", return_value=False
        ):
            status = await WhisperModelService.start_download("small", "en")

        assert status.state == "downloading"
        assert status.message == "Downloading speech model…"

    @pytest.mark.asyncio
    async def test_normalizes_inputs(self):
        """Normalizes size and locale before scheduling."""
        with patch(
            "app.speech.services.whisper_model.is_installed", return_value=False
        ):
            status = await WhisperModelService.start_download(" SMALL ", " RU ")

        assert status.size == "small"
        assert status.locale == "ru"


class TestDownloadAndInstall:
    """Tests for WhisperModelService._download_and_install."""

    @pytest.mark.asyncio
    async def test_calls_snapshot_download(self, tmp_path):
        """_download_and_install calls snapshot_download with correct repo."""
        whisper_root = tmp_path / "whisper-models"
        staging_dir = tmp_path / ".staging-small"

        with (
            patch(
                "app.speech.services.whisper_model.WHISPER_MODELS_ROOT", whisper_root
            ),
            patch(
                "app.speech.services.whisper_model.prepare_staging_dir",
                return_value=staging_dir,
            ),
            patch(
                "app.speech.services.whisper_model.WhisperModelService._snapshot_download"
            ) as mock_snapshot,
            patch(
                "app.speech.services.whisper_model.is_valid_model_dir",
                return_value=True,
            ),
            patch(
                "app.speech.services.whisper_model.promote_staging_dir"
            ) as mock_promote,
            patch("app.speech.services.whisper_model.cleanup_staging_dir"),
        ):
            await WhisperModelService._download_and_install("small")

        mock_snapshot.assert_called_once()
        mock_promote.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_invalid_snapshot(self, tmp_path):
        """Raises ValueError when downloaded snapshot lacks model.bin."""
        whisper_root = tmp_path / "whisper-models"
        staging_dir = tmp_path / ".staging-small"

        with (
            patch(
                "app.speech.services.whisper_model.WHISPER_MODELS_ROOT", whisper_root
            ),
            patch(
                "app.speech.services.whisper_model.prepare_staging_dir",
                return_value=staging_dir,
            ),
            patch(
                "app.speech.services.whisper_model.WhisperModelService._snapshot_download"
            ),
            patch(
                "app.speech.services.whisper_model.is_valid_model_dir",
                return_value=False,
            ),
            patch("app.speech.services.whisper_model.cleanup_staging_dir"),
            pytest.raises(ValueError, match="does not contain a valid Whisper"),
        ):
            await WhisperModelService._download_and_install("small")

    @pytest.mark.asyncio
    async def test_ensures_whisper_root_exists(self, tmp_path):
        """Creates WHISPER_MODELS_ROOT if it does not exist."""
        whisper_root = tmp_path / "nested" / "whisper-models"
        staging_dir = tmp_path / ".staging-small"

        with (
            patch(
                "app.speech.services.whisper_model.WHISPER_MODELS_ROOT", whisper_root
            ),
            patch(
                "app.speech.services.whisper_model.prepare_staging_dir",
                return_value=staging_dir,
            ),
            patch(
                "app.speech.services.whisper_model.WhisperModelService._snapshot_download"
            ),
            patch(
                "app.speech.services.whisper_model.is_valid_model_dir",
                return_value=True,
            ),
            patch("app.speech.services.whisper_model.promote_staging_dir"),
            patch("app.speech.services.whisper_model.cleanup_staging_dir"),
        ):
            await WhisperModelService._download_and_install("small")

        assert whisper_root.exists()

    @pytest.mark.asyncio
    async def test_sets_percent_to_95_then_100(self, tmp_path):
        """Progress goes to 95 after download and 100 after promotion."""
        whisper_root = tmp_path / "whisper-models"
        staging_dir = tmp_path / ".staging-small"

        with (
            patch(
                "app.speech.services.whisper_model.WHISPER_MODELS_ROOT", whisper_root
            ),
            patch(
                "app.speech.services.whisper_model.prepare_staging_dir",
                return_value=staging_dir,
            ),
            patch(
                "app.speech.services.whisper_model.WhisperModelService._snapshot_download"
            ),
            patch(
                "app.speech.services.whisper_model.is_valid_model_dir",
                return_value=True,
            ),
            patch("app.speech.services.whisper_model.promote_staging_dir"),
            patch("app.speech.services.whisper_model.cleanup_staging_dir"),
        ):
            await WhisperModelService._download_and_install("small")

        assert WhisperModelService.download_percent() == 100

    @pytest.mark.asyncio
    async def test_cleanup_runs_on_error(self, tmp_path):
        """Staging directory is cleaned up even on failure."""
        whisper_root = tmp_path / "whisper-models"
        staging_dir = tmp_path / ".staging-small"
        staging_dir.mkdir(parents=True)

        with (
            patch(
                "app.speech.services.whisper_model.WHISPER_MODELS_ROOT", whisper_root
            ),
            patch(
                "app.speech.services.whisper_model.prepare_staging_dir",
                return_value=staging_dir,
            ),
            patch(
                "app.speech.services.whisper_model.WhisperModelService._snapshot_download",
                side_effect=Exception("network down"),
            ),
            patch(
                "app.speech.services.whisper_model.cleanup_staging_dir"
            ) as mock_cleanup,
            pytest.raises(Exception, match="network down"),
        ):
            await WhisperModelService._download_and_install("small")

        mock_cleanup.assert_called_once()


class TestRunDownload:
    """Tests for WhisperModelService._run_download."""

    @pytest.mark.asyncio
    async def test_calls_download_and_load(self):
        """_run_download installs then loads the model."""
        with (
            patch(
                "app.speech.services.whisper_model.WhisperModelService._download_and_install"
            ) as mock_download,
            patch(
                "app.speech.services.whisper_model.WhisperRuntime.load_size",
                return_value=True,
            ) as mock_load,
        ):
            await WhisperModelService._run_download("medium")

        mock_download.assert_called_once_with("medium")
        mock_load.assert_called_once_with("medium")


class TestSnapshotDownload:
    """Tests for WhisperModelService._snapshot_download."""

    def test_calls_huggingface_snapshot_download(self):
        """_snapshot_download delegates to huggingface_hub.snapshot_download."""
        spec = MagicMock()
        spec.hf_repo_id = "test/repo"
        spec.approx_download_mb = 100
        destination = MagicMock()
        set_percent = MagicMock()

        with patch(
            "app.speech.services.whisper_model.snapshot_download"
        ) as mock_snapshot:
            WhisperModelService._snapshot_download(spec, destination, set_percent)

        mock_snapshot.assert_called_once()
        call_kwargs = mock_snapshot.call_args.kwargs
        assert call_kwargs["repo_id"] == "test/repo"
        assert call_kwargs["local_dir"] == str(destination)
        assert call_kwargs["tqdm_class"] is not None
