# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SaveConfigUseCase."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.platform.domain.config import AppConfig, ConfigService
from app.platform.use_cases.save_config import SaveConfigUseCase


def _config() -> AppConfig:
    return AppConfig(
        provider_type="openai-compatible",
        base_url="http://localhost",
        model="gpt-4",
        speech_model_size="small",
    )


def make_coordinator(*, speech_errors: tuple[str, ...] = ()) -> MagicMock:
    """Build a coordinator mock whose reload reports the given errors."""
    coordinator = MagicMock()
    coordinator.reload_after_config_save = AsyncMock(return_value=list(speech_errors))
    return coordinator


class TestSaveConfigUseCase:
    """Tests for the save-config orchestration."""

    @pytest.mark.asyncio
    async def test_saves_config_and_reloads_speech(self):
        """Config is persisted and speech runtimes are reloaded."""
        coordinator = make_coordinator()
        use_case = SaveConfigUseCase(ConfigService, coordinator)

        with patch.object(ConfigService, "save_config") as mock_save:
            result = await use_case.execute(_config())

        mock_save.assert_called_once_with(_config())
        coordinator.reload_after_config_save.assert_awaited_once_with(_config())
        assert result.saved is True
        assert result.speech_errors == ()

    @pytest.mark.asyncio
    async def test_saves_config_even_when_speech_fails(self):
        """Config is still saved when a speech model fails to load."""
        coordinator = make_coordinator(speech_errors=("Whisper failed to load",))
        use_case = SaveConfigUseCase(ConfigService, coordinator)

        with patch.object(ConfigService, "save_config") as mock_save:
            result = await use_case.execute(_config())

        mock_save.assert_called_once_with(_config())
        assert result.saved is True
        assert result.speech_errors == ("Whisper failed to load",)
