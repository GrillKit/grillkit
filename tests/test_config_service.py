# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for configuration service."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.llm_models import LLMModelEntry
from app.platform.services.config import AppConfig, ConfigService


@pytest.fixture
def config_path(tmp_path):
    """Fixture for configuration file path."""
    test_config_path = tmp_path / "test_config.json"
    yield test_config_path
    if test_config_path.exists():
        test_config_path.unlink()


@pytest.fixture
def mock_provider_factory():
    """Fixture for mocking ProviderFactory."""
    with patch("app.platform.services.config.ProviderFactory") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.validate.return_value = True
        mock_provider.close = AsyncMock()
        mock_factory.from_config.return_value = mock_provider
        yield mock_factory


class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_to_dict(self):
        """Test to_dict method masks API key correctly."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            timeout=30.0,
        )
        assert config.to_dict(mask_secret=False) == {
            "provider_type": "openai-compatible",
            "base_url": "http://localhost",
            "model": "gpt-4",
            "api_key": "test_key",
            "timeout": 30.0,
            "locale": "en",
            "speech_model_size": "small",
            "question_voice_enabled": False,
            "tts_voice_id": "en_US-lessac-medium",
            "llm_preset_id": None,
        }
        assert config.to_dict(mask_secret=True)["api_key"] == "***"

    def test_to_storage_dict(self):
        """Application settings persist without LLM fields."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            llm_preset_id="cloud",
        )
        assert config.to_storage_dict() == {
            "timeout": 60.0,
            "locale": "en",
            "speech_model_size": "small",
            "question_voice_enabled": False,
            "tts_voice_id": "en_US-lessac-medium",
        }

    def test_from_dict(self):
        """Test from_dict reads application settings only."""
        data = {
            "timeout": 30.0,
            "locale": "en",
            "speech_model_size": "medium",
            "question_voice_enabled": True,
        }
        config = AppConfig.from_dict(data)
        assert config.provider_type == "openai-compatible"
        assert config.base_url == ""
        assert config.model == ""
        assert config.api_key is None
        assert config.timeout == 30.0
        assert config.locale == "en"
        assert config.speech_model_size == "medium"
        assert config.question_voice_enabled is True

    def test_from_dict_question_voice_enabled(self):
        """Test from_dict reads question_voice_enabled when present."""
        data = {"question_voice_enabled": True}
        config = AppConfig.from_dict(data)
        assert config.question_voice_enabled is True

    def test_from_dict_defaults(self):
        """Test from_dict uses default values when keys are missing."""
        config = AppConfig.from_dict({})
        assert config.provider_type == "openai-compatible"
        assert config.api_key is None
        assert config.timeout == 60.0
        assert config.locale == "en"
        assert config.speech_model_size == "small"
        assert config.question_voice_enabled is False

    def test_effective_uses_catalog_base_url(self, monkeypatch):
        """effective() applies catalog model and base URL."""
        entry = LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.example.com/v1",
            api_key_required=True,
            api_key="secret",
        )
        monkeypatch.setattr(
            "app.platform.services.config.LLMCatalogService.get_model",
            lambda _model_id: entry,
        )
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="",
            model="ignored",
            llm_preset_id="cloud",
        )
        effective = config.effective()
        assert effective.base_url == "https://api.example.com/v1"
        assert effective.model == "gpt-4"
        assert effective.api_key == "secret"

    def test_from_dict_normalizes_locale(self):
        """Test from_dict normalizes locale codes."""
        data = {"locale": " RU "}
        config = AppConfig.from_dict(data)
        assert config.locale == "ru"

    def test_resolve_api_key_from_form_uses_catalog_key(self, monkeypatch):
        """Blank form values preserve API keys stored in the model catalog."""
        entry = LLMModelEntry(
            id="work",
            display_name="Work",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.example.com/v1",
            api_key_required=True,
            api_key="catalog-secret",
        )
        monkeypatch.setattr(
            "app.platform.services.config.LLMCatalogService.get_model",
            lambda _model_id: entry,
        )
        assert AppConfig.resolve_api_key_from_form("", "work") == "catalog-secret"

    def test_resolve_api_key_from_form_accepts_new_key(self):
        """Non-empty form value replaces the stored API key."""
        assert AppConfig.resolve_api_key_from_form("new-key", "work") == "new-key"

    def test_resolve_api_key_from_form_clears_when_empty_and_no_catalog_key(
        self, monkeypatch
    ):
        """Empty form with no stored catalog key yields no API key."""
        entry = LLMModelEntry(
            id="work",
            display_name="Work",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.example.com/v1",
            api_key_required=False,
        )
        monkeypatch.setattr(
            "app.platform.services.config.LLMCatalogService.get_model",
            lambda _model_id: entry,
        )
        assert AppConfig.resolve_api_key_from_form("", "work") is None

    def test_from_dict_rejects_unknown_locale(self):
        """Test from_dict raises for unsupported locale."""
        data = {"locale": "xx"}
        with pytest.raises(ValueError, match="Unsupported locale"):
            AppConfig.from_dict(data)


class TestConfigService:
    """Tests for ConfigService class."""

    @pytest.fixture
    def mock_config_path(self, tmp_path, monkeypatch):
        """Fixture providing patched config and catalog paths in a temp directory."""
        test_path = tmp_path / "test_config.json"
        catalog_path = tmp_path / "llm_models.json"
        catalog_path.write_text(
            json.dumps(
                {
                    "selected": "cloud",
                    "models": {
                        "cloud": {
                            "display_name": "Cloud",
                            "provider_type": "openai-compatible",
                            "model": "gpt-4",
                            "base_url": "http://localhost",
                            "api_key_required": True,
                            "api_key": "test_key",
                        }
                    },
                }
            )
        )
        monkeypatch.setattr("app.platform.services.config.CONFIG_PATH", test_path)
        monkeypatch.setattr(
            "app.platform.services.llm_catalog.LLM_MODELS_PATH", catalog_path
        )
        yield test_path

    def test_save_and_get_config(self, mock_config_path):
        """Test saving app settings and selected model."""
        _config_path = mock_config_path
        user_path = _config_path.parent / "llm_models.json"
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            llm_preset_id="cloud",
        )
        ConfigService.save_config(config)

        retrieved_config = ConfigService.get_config()
        assert retrieved_config is not None
        assert retrieved_config.llm_preset_id == "cloud"
        assert retrieved_config.model == "gpt-4"
        stored = json.loads(_config_path.read_text())
        assert "llm_preset_id" not in stored
        assert "base_url" not in stored
        llm_data = json.loads(user_path.read_text())
        assert llm_data["selected"] == "cloud"

    def test_get_config_no_file(self, mock_config_path):
        """Test retrieving config when file does not exist."""
        assert ConfigService.get_config() is None

    def test_delete_config(self, mock_config_path):
        """Test deleting configuration file."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
        )
        ConfigService.save_config(config)
        assert mock_config_path.exists()

        ConfigService.delete_config()
        assert not mock_config_path.exists()

    @pytest.mark.asyncio
    async def test_test_connection_success(
        self, mock_config_path, mock_provider_factory, monkeypatch
    ):
        """Test successful provider connection."""
        entry = LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="http://localhost",
            api_key_required=True,
            api_key="test_key",
        )
        monkeypatch.setattr(
            "app.platform.services.config.LLMCatalogService.get_model",
            lambda _model_id: entry,
        )
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            llm_preset_id="cloud",
        )
        success, message = await ConfigService.test_connection(config)
        assert success is True
        assert message == "Connection successful"
        mock_provider_factory.from_config.assert_called_once_with(
            api_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            timeout=60.0,
        )
        mock_provider_factory.from_config.return_value.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure_invalid_api_key(
        self, mock_config_path, mock_provider_factory, monkeypatch
    ):
        """Test failed provider connection due to invalid API key."""
        entry = LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="http://localhost",
            api_key_required=True,
            api_key="invalid_key",
        )
        monkeypatch.setattr(
            "app.platform.services.config.LLMCatalogService.get_model",
            lambda _model_id: entry,
        )
        mock_provider_factory.from_config.return_value.validate.side_effect = (
            ValueError("Authentication failed: Invalid API key")
        )
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="invalid_key",
            llm_preset_id="cloud",
        )
        success, message = await ConfigService.test_connection(config)
        assert success is False
        assert message == "Authentication failed: Invalid API key"

    @pytest.mark.asyncio
    async def test_test_connection_exception(
        self, mock_config_path, mock_provider_factory, monkeypatch
    ):
        """Test failed provider connection due to an exception."""
        entry = LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="http://localhost",
            api_key_required=True,
            api_key="test_key",
        )
        monkeypatch.setattr(
            "app.platform.services.config.LLMCatalogService.get_model",
            lambda _model_id: entry,
        )
        mock_provider_factory.from_config.side_effect = ValueError("Test Error")
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            llm_preset_id="cloud",
        )
        success, message = await ConfigService.test_connection(config)
        assert success is False
        assert message == "Test Error"

    @pytest.mark.asyncio
    async def test_create_provider_from_config_success(
        self, mock_config_path, mock_provider_factory
    ):
        """Test creating provider from saved config."""
        user_path = mock_config_path.parent / "llm_models.json"
        user_path.write_text(
            json.dumps(
                {
                    "selected": "cloud",
                    "models": {
                        "cloud": {
                            "display_name": "Cloud",
                            "provider_type": "openai-compatible",
                            "model": "gpt-4",
                            "base_url": "http://localhost",
                            "api_key_required": True,
                            "api_key": "test_key",
                        }
                    },
                }
            )
        )
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            llm_preset_id="cloud",
        )
        ConfigService.save_config(config)

        provider = ConfigService.create_provider_from_config()
        assert provider is not None
        mock_provider_factory.from_config.assert_called_once_with(
            api_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
            timeout=60.0,
        )

    @pytest.mark.asyncio
    async def test_create_provider_from_config_no_config(self, mock_config_path):
        """Test creating provider when no config exists."""
        if mock_config_path.exists():
            mock_config_path.unlink()  # Ensure no config file exists
        with pytest.raises(ValueError, match="No configuration found"):
            ConfigService.create_provider_from_config()

    def test_check_whisper_ready_when_missing(self, monkeypatch):
        """Audio-enabled save is blocked when Whisper is not installed."""
        monkeypatch.setattr(
            "app.platform.services.config.is_installed",
            lambda _size: False,
        )
        ok, message = ConfigService.check_whisper_ready("small")
        assert ok is False
        assert "not installed" in message

    @pytest.mark.asyncio
    async def test_test_audio_connection_success(
        self, mock_provider_factory, monkeypatch
    ):
        """Audio probe succeeds when the provider accepts WAV input."""
        mock_provider = AsyncMock()
        mock_provider.probe_audio_input.return_value = True
        mock_provider.close = AsyncMock()
        mock_provider_factory.from_config.return_value = mock_provider
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4o",
            api_key="test_key",
        )
        success, message = await ConfigService.test_audio_connection(config)
        assert success is True
        assert message == "Audio connection successful"
        mock_provider.probe_audio_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_interview_model_audio_requires_whisper(
        self, mock_provider_factory, monkeypatch
    ):
        """Audio catalog entries require an installed Whisper model."""
        mock_provider_factory.from_config.return_value.validate = AsyncMock(
            return_value=True
        )
        mock_provider_factory.from_config.return_value.close = AsyncMock()
        monkeypatch.setattr(
            "app.platform.services.config.is_installed",
            lambda _size: False,
        )
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4o",
            api_key="test_key",
        )
        success, message = await ConfigService.test_interview_model(
            config,
            accepts_audio_input=True,
        )
        assert success is False
        assert "Whisper" in message
