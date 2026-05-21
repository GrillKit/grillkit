# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Whisper runtime loading."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.whisper_runtime import WhisperRuntime


@pytest.fixture(autouse=True)
def reset_runtime():
    """Clear runtime state between tests."""
    WhisperRuntime.unload()
    WhisperRuntime._load_error = None
    yield
    WhisperRuntime.unload()


class TestWhisperRuntime:
    """Tests for in-process Whisper model lifecycle."""

    @pytest.mark.asyncio
    async def test_load_size_success(self, tmp_path):
        """load_size stores model and size when installation exists."""
        model_dir = tmp_path / "small"
        model_dir.mkdir()
        (model_dir / "model.bin").write_bytes(b"x")
        mock_model = MagicMock()

        with (
            patch("app.services.whisper_runtime.model_dir", return_value=model_dir),
            patch("app.services.whisper_runtime.is_installed", return_value=True),
            patch(
                "app.services.whisper_runtime.WhisperRuntime._load_model_sync",
                return_value=mock_model,
            ),
        ):
            loaded = await WhisperRuntime.load_size("small")

        assert loaded is True
        assert WhisperRuntime.is_loaded("small")
        assert WhisperRuntime.loaded_size() == "small"

    @pytest.mark.asyncio
    async def test_load_size_missing_unloads(self):
        """load_size clears memory when the model is not installed."""
        with patch("app.services.whisper_runtime.is_installed", return_value=False):
            loaded = await WhisperRuntime.load_size("small")

        assert loaded is False
        assert WhisperRuntime.loaded_size() is None
