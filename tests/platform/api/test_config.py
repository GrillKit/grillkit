# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for platform config HTTP routes."""

from unittest.mock import patch

import pytest

from app.ai.llm_models import LLMModelEntry
from app.platform.services.config import AppConfig


class TestConfigRouter:
    """Tests for config router endpoints."""

    _catalog_entry = LLMModelEntry(
        id="cloud",
        display_name="Cloud",
        provider_type="openai-compatible",
        model="gpt-4",
        base_url="https://api.openai.com",
        api_key_required=True,
        api_key="stored-secret",
    )

    def _config_form_data(self, **overrides):
        """Build a valid config form payload."""
        data = {
            "llm_preset_id": "cloud",
            "api_key": "test-key",
            "timeout": 60.0,
            "locale": "en",
        }
        data.update(overrides)
        return data

    def test_config_page_get(self, client):
        """Test GET /config endpoint returns HTML."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="https://api.openai.com",
            model="gpt-4",
            api_key="test-key",
        )

        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
        ):
            response = client.get("/config")
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
            assert "Interview model" in response.text
            assert "Add model to catalog" in response.text

    def test_config_page_get_no_config(self, client):
        """Test GET /config without existing config."""
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
        ):
            response = client.get("/config")
            assert response.status_code == 200
            assert "Interview model" in response.text
            assert "Speech recognition model" in response.text
            assert "Question voice (TTS)" in response.text

    async def test_save_config_preserves_api_key_when_field_empty(self, client):
        """POST /config keeps the stored key when the password field is left blank."""
        existing = AppConfig(
            provider_type="openai-compatible",
            base_url="https://api.openai.com",
            model="gpt-4",
            api_key="stored-secret",
            llm_preset_id="cloud",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=existing,
            ),
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.save_config"
            ) as mock_save,
        ):
            response = client.post(
                "/config",
                data=self._config_form_data(api_key=""),
            )

        assert response.status_code == 200
        saved = mock_save.call_args[0][0]
        assert saved.api_key == "stored-secret"

    @pytest.mark.asyncio
    async def test_save_config_success(self, client):
        """Test POST /config with successful connection test."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.save_config"
            ) as mock_save,
        ):
            response = client.post(
                "/config",
                data=self._config_form_data(),
            )

            assert response.status_code == 200
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_config_failure(self, client):
        """Test POST /config with failed connection test."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(False, "Connection failed"),
            ),
        ):
            response = client.post(
                "/config",
                data=self._config_form_data(),
            )

            assert response.status_code == 200

    def test_delete_config(self, client):
        """Test DELETE /config endpoint."""
        with (
            patch(
                "app.platform.services.config.ConfigService.delete_config"
            ) as mock_delete,
        ):
            response = client.delete("/config")

            assert response.status_code == 200
            mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_config_success(self, client):
        """Test POST /config/test with successful connection."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "Connection successful"),
            ),
        ):
            response = client.post(
                "/config/test",
                data=self._config_form_data(),
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_test_config_failure(self, client):
        """Test POST /config/test with failed connection."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(False, "Invalid API key"),
            ),
        ):
            response = client.post(
                "/config/test",
                data=self._config_form_data(api_key="invalid-key"),
            )

            assert response.status_code == 200
