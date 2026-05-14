# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for AI provider factory."""

import pytest
from unittest.mock import patch

from app.ai.factory import ProviderFactory
from app.ai.openai_compatible import OpenAICompatibleProvider


class TestProviderFactory:
    """Tests for ProviderFactory class."""

    def test_from_config_openai_compatible(self):
        """Test creating an OpenAI-compatible provider."""
        with patch("app.ai.factory.OpenAICompatibleProvider") as MockProvider:
            mock_instance = MockProvider.return_value

            result = ProviderFactory.from_config(
                base_url="https://api.openai.com/v1",
                model="gpt-4",
                api_key="test-key",
                api_type="openai-compatible",
                timeout=30.0,
            )

            MockProvider.assert_called_once_with(
                model="gpt-4",
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                timeout=30.0,
            )
            assert result == mock_instance

    def test_from_config_without_api_key(self):
        """Test creating a provider without API key for local providers."""
        with patch("app.ai.factory.OpenAICompatibleProvider") as MockProvider:
            mock_instance = MockProvider.return_value

            result = ProviderFactory.from_config(
                base_url="http://localhost:11434",
                model="llama2",
                api_type="openai-compatible",
            )

            MockProvider.assert_called_once_with(
                model="llama2",
                base_url="http://localhost:11434",
                api_key=None,
            )
            assert result == mock_instance

    def test_from_config_unsupported_type(self):
        """Test that unsupported api_type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported API type: anthropic"):
            ProviderFactory.from_config(
                base_url="https://api.anthropic.com",
                model="claude-3",
                api_type="anthropic",
            )

    def test_from_config_case_sensitive(self):
        """Test that api_type is case-sensitive."""
        with pytest.raises(ValueError, match="Unsupported API type: OpenAI-Compatible"):
            ProviderFactory.from_config(
                base_url="https://api.openai.com/v1",
                model="gpt-4",
                api_type="OpenAI-Compatible",
            )

    def test_get_provider_types(self):
        """Test listing available provider types."""
        types = ProviderFactory.get_provider_types()

        assert isinstance(types, list)
        assert len(types) == 1

        provider_type = types[0]
        assert provider_type["id"] == "openai-compatible"
        assert provider_type["name"] == "OpenAI Compatible"
        assert "description" in provider_type
        assert "OpenAI" in provider_type["description"]
