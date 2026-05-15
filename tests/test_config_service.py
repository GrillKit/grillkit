# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for configuration service."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.config import ConfigService, ProviderConfig


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
    with patch("app.services.config.ProviderFactory") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.validate.return_value = True
        mock_factory.from_config.return_value = mock_provider
        yield mock_factory


class TestProviderConfig:
    """Tests for ProviderConfig dataclass."""

    def test_to_dict(self):
        """Test to_dict method masks API key correctly."""
        config = ProviderConfig(
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
        }
        assert config.to_dict(mask_secret=True) == {
            "provider_type": "openai-compatible",
            "base_url": "http://localhost",
            "model": "gpt-4",
            "api_key": "***",
            "timeout": 30.0,
        }

    def test_from_dict(self):
        """Test from_dict method creates instance correctly."""
        data = {
            "provider_type": "openai-compatible",
            "base_url": "http://localhost",
            "model": "gpt-4",
            "api_key": "test_key",
            "timeout": 30.0,
        }
        config = ProviderConfig.from_dict(data)
        assert config.provider_type == "openai-compatible"
        assert config.base_url == "http://localhost"
        assert config.model == "gpt-4"
        assert config.api_key == "test_key"
        assert config.timeout == 30.0

    def test_from_dict_defaults(self):
        """Test from_dict uses default values when keys are missing."""
        data = {
            "base_url": "http://localhost",
            "model": "gpt-4",
        }
        config = ProviderConfig.from_dict(data)
        assert config.provider_type == "openai-compatible"
        assert config.api_key is None
        assert config.timeout == 60.0


class TestConfigService:
    """Tests for ConfigService class."""

    @pytest.fixture
    def mock_config_path(self, tmp_path):
        """Fixture providing a patched CONFIG_PATH in a temp directory."""
        test_path = tmp_path / "test_config.json"
        with patch("app.services.config.CONFIG_PATH", test_path):
            yield test_path

    def test_save_and_get_config(self, mock_config_path, config_path):
        """Test saving and retrieving configuration."""
        config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
        )
        ConfigService.save_config(config)
        
        retrieved_config = ConfigService.get_config()
        assert retrieved_config == config
        assert mock_config_path.exists()

    def test_get_config_no_file(self, mock_config_path):
        """Test retrieving config when file does not exist."""
        assert ConfigService.get_config() is None

    def test_delete_config(self, mock_config_path, config_path):
        """Test deleting configuration file."""
        config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
        )
        ConfigService.save_config(config)
        assert config_path.exists()

        ConfigService.delete_config()
        assert not config_path.exists()

    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_config_path, mock_provider_factory):
        """Test successful provider connection."""
        config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
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
    async def test_test_connection_failure_invalid_api_key(self, mock_config_path, mock_provider_factory):
        """Test failed provider connection due to invalid API key."""
        mock_provider_factory.from_config.return_value.validate.side_effect = ValueError("Authentication failed: Invalid API key")
        config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="invalid_key",
        )
        success, message = await ConfigService.test_connection(config)
        assert success is False
        assert message == "Authentication failed: Invalid API key"

    @pytest.mark.asyncio
    async def test_test_connection_exception(self, mock_config_path, mock_provider_factory):
        """Test failed provider connection due to an exception."""
        mock_provider_factory.from_config.side_effect = ValueError("Test Error")
        config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
        )
        success, message = await ConfigService.test_connection(config)
        assert success is False
        assert message == "Test Error"

    @pytest.mark.asyncio
    async def test_create_provider_from_config_success(self, mock_config_path, mock_provider_factory):
        """Test creating provider from saved config."""
        config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            api_key="test_key",
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
