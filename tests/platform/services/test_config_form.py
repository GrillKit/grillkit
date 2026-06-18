# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for ConfigFormService parsing and connection testing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.llm_models import LLMModelEntry
from app.platform.services.config import AppConfig
from app.platform.services.config_form import ConfigFormService


class TestParseAndTest:
    """Tests for ConfigFormService.parse_and_test."""

    @pytest.fixture
    def mock_catalog(self, monkeypatch):
        """Patch LLMCatalogService with a minimal catalog."""
        entry = LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.example.com/v1",
            api_key_required=True,
        )
        catalog = MagicMock()
        catalog.models = {"cloud": entry}
        with (
            patch(
                "app.platform.services.config_form.LLMCatalogService.get_model",
                return_value=entry,
            ) as mock_get,
            patch(
                "app.platform.services.config_form.LLMCatalogService.load_catalog",
                return_value=catalog,
            ),
        ):
            yield mock_get, entry

    @pytest.fixture
    def mock_config_service(self):
        """Build a mock ConfigService class."""
        mock_service = MagicMock()
        mock_service.get_config.return_value = None
        mock_service.test_interview_model = AsyncMock(return_value=(True, "OK"))
        return mock_service

    @pytest.mark.asyncio
    async def test_parse_and_test_success(self, mock_catalog, mock_config_service):
        """Valid form data yields config, success=True, and message."""
        _, entry = mock_catalog
        config, success, message = await ConfigFormService.parse_and_test(
            config_service=mock_config_service,
            llm_preset_id="cloud",
            api_key="secret",
            timeout=30.0,
            locale="en",
            speech_model_size="small",
            question_voice_enabled=True,
        )
        assert isinstance(config, AppConfig)
        assert config.provider_type == "openai-compatible"
        assert config.model == "gpt-4"
        assert config.api_key == "secret"
        assert config.locale == "en"
        assert config.speech_model_size == "small"
        assert config.question_voice_enabled is True
        assert success is True
        assert message == "OK"
        mock_config_service.test_interview_model.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_parse_and_test_uses_existing_voice_when_locale_unchanged(
        self, mock_catalog, mock_config_service
    ):
        """Existing tts_voice_id is preserved when locale matches."""
        existing = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="ru",
            tts_voice_id="ru_RU-dmitri-medium",
        )
        mock_config_service.get_config.return_value = existing

        config, success, message = await ConfigFormService.parse_and_test(
            config_service=mock_config_service,
            llm_preset_id="cloud",
            api_key="secret",
            timeout=30.0,
            locale="ru",
            speech_model_size="small",
            question_voice_enabled=False,
        )
        assert config.tts_voice_id == "ru_RU-dmitri-medium"

    @pytest.mark.asyncio
    async def test_parse_and_test_selects_voice_by_locale_when_locale_changes(
        self, mock_catalog, mock_config_service
    ):
        """New locale triggers default voice selection."""
        existing = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            tts_voice_id="en_US-lessac-medium",
        )
        mock_config_service.get_config.return_value = existing

        config, success, message = await ConfigFormService.parse_and_test(
            config_service=mock_config_service,
            llm_preset_id="cloud",
            api_key="secret",
            timeout=30.0,
            locale="fr",
            speech_model_size="small",
            question_voice_enabled=False,
        )
        assert config.tts_voice_id == "fr_FR-siwis-medium"

    @pytest.mark.asyncio
    async def test_parse_and_test_rejects_invalid_preset(self, mock_config_service):
        """Invalid llm_preset_id falls back to existing or default config."""
        with (
            patch(
                "app.platform.services.config_form.LLMCatalogService.load_catalog",
                return_value=MagicMock(),
            ),
            patch(
                "app.platform.services.config_form.normalize_model_id",
                side_effect=ValueError("Unsupported LLM model"),
            ),
        ):
            config, success, message = await ConfigFormService.parse_and_test(
                config_service=mock_config_service,
                llm_preset_id="invalid",
                api_key="",
                timeout=60.0,
                locale="en",
                speech_model_size="small",
                question_voice_enabled=False,
            )
        assert success is False
        assert "Unsupported LLM model" in message
        assert config is not None

    @pytest.mark.asyncio
    async def test_parse_and_test_rejects_missing_model_entry(
        self, mock_config_service
    ):
        """Catalog entry not found returns failure with fallback config."""
        with (
            patch(
                "app.platform.services.config_form.LLMCatalogService.load_catalog",
                return_value=MagicMock(),
            ),
            patch(
                "app.platform.services.config_form.LLMCatalogService.get_model",
                return_value=None,
            ),
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
        ):
            config, success, message = await ConfigFormService.parse_and_test(
                config_service=mock_config_service,
                llm_preset_id="cloud",
                api_key="",
                timeout=60.0,
                locale="en",
                speech_model_size="small",
                question_voice_enabled=False,
            )
        assert success is False
        assert "Interview model not found" in message

    @pytest.mark.asyncio
    async def test_parse_and_test_connection_failure(
        self, mock_catalog, mock_config_service
    ):
        """Connection test failure is returned with config."""
        mock_config_service.test_interview_model = AsyncMock(
            return_value=(False, "Connection refused")
        )

        config, success, message = await ConfigFormService.parse_and_test(
            config_service=mock_config_service,
            llm_preset_id="cloud",
            api_key="bad",
            timeout=30.0,
            locale="en",
            speech_model_size="small",
            question_voice_enabled=False,
        )
        assert success is False
        assert message == "Connection refused"
        assert config.provider_type == "openai-compatible"

    @pytest.mark.asyncio
    async def test_parse_and_test_normalizes_inputs(
        self, mock_catalog, mock_config_service
    ):
        """Locale and speech_model_size are normalized."""
        _, entry = mock_catalog
        config, success, message = await ConfigFormService.parse_and_test(
            config_service=mock_config_service,
            llm_preset_id="cloud",
            api_key="",
            timeout=60.0,
            locale=" RU ",
            speech_model_size=" SMALL ",
            question_voice_enabled=True,
        )
        assert config.locale == "ru"
        assert config.speech_model_size == "small"
        assert config.tts_voice_id == "ru_RU-dmitri-medium"
