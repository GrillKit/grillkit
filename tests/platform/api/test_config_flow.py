# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for first-time configuration flow (S1 scenarios)."""

from unittest.mock import patch

from app.ai.llm_models import LLMModelEntry
from app.platform.services.config import AppConfig


class TestFirstTimeConfigFlow:
    """S1: First-time Configuration Flow."""

    def _catalog_entry(self):
        return LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.openai.com",
            api_key_required=True,
            api_key="stored-secret",
        )

    def test_dashboard_renders_without_config(self, client):
        """S1.1: GET / renders dashboard even without provider config."""
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch(
                "app.interview.services.dashboard.DashboardBuilder.list_rows",
                return_value=[],
            ),
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_setup_redirects_without_config(self, client):
        """S1.2: GET /setup redirects to /config when no provider config."""
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=None,
        ):
            response = client.get("/setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/config"

    def test_config_save_empty_fields_returns_422(self, client):
        """S1.3: POST /config with empty required fields returns 422 validation error."""
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=None,
        ):
            response = client.post(
                "/config",
                data={
                    "llm_preset_id": "",
                    "api_key": "",
                    "timeout": "",
                    "locale": "en",
                },
            )
        # FastAPI form validation returns 422 for empty required strings
        assert response.status_code == 422

    def test_config_save_fails_with_unreachable_ollama(self, client):
        """S1.4: Save with unreachable Ollama shows connection error."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="local",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=None,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(False, "Connection refused"),
            ),
        ):
            response = client.post(
                "/config",
                data={
                    "llm_preset_id": "local",
                    "base_url": "http://localhost:11434/v1",
                    "model": "llama3",
                    "api_key": "",
                    "timeout": "60",
                    "locale": "en",
                },
            )
        assert response.status_code == 200
        assert (
            "connection refused" in response.text.lower()
            or "error" in response.text.lower()
        )

    def test_config_test_connection_success(self, client):
        """S1.5: POST /config/test returns success with valid provider."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry(),
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "Connection successful"),
            ),
        ):
            response = client.post(
                "/config/test",
                data={
                    "llm_preset_id": "cloud",
                    "api_key": "test-key",
                    "timeout": "60",
                    "locale": "en",
                },
            )
        assert response.status_code == 200
        assert "successful" in response.text.lower()

    def test_config_test_connection_failure(self, client):
        """S1.5: POST /config/test returns error with invalid provider."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry(),
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(False, "Invalid API key"),
            ),
        ):
            response = client.post(
                "/config/test",
                data={
                    "llm_preset_id": "cloud",
                    "api_key": "bad-key",
                    "timeout": "60",
                    "locale": "en",
                },
            )
        assert response.status_code == 200
        assert "error" in response.text.lower() or "invalid" in response.text.lower()

    def test_add_model_to_catalog_success(self, client):
        """S1.6: Add a new model to catalog via POST /config/llm-models."""
        with (
            patch(
                "app.platform.services.config.ConfigService.test_catalog_model",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch(
                "app.platform.services.llm_catalog.LLMCatalogService.add_user_model",
                return_value=self._catalog_entry(),
            ) as mock_add,
        ):
            response = client.post(
                "/config/llm-models",
                data={
                    "display_name": "GPT-4 Test",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4",
                    "api_key": "test-key",
                    "api_key_required": "on",
                },
            )
        assert response.status_code == 200
        mock_add.assert_called_once()
        assert "added" in response.text.lower() or "gpt-4 test" in response.text.lower()

    def test_add_model_to_catalog_rejects_invalid_url(self, client):
        """S1.6: Adding model with invalid URL fails validation."""
        with (
            patch(
                "app.platform.services.config.ConfigService.test_catalog_model",
                return_value=(False, "Connection refused"),
            ),
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
        ):
            response = client.post(
                "/config/llm-models",
                data={
                    "display_name": "Broken",
                    "base_url": "http://invalid-url-test",
                    "model": "none",
                    "api_key": "",
                    "api_key_required": "",
                },
            )
        assert response.status_code == 200
        assert "error" in response.text.lower() or "refused" in response.text.lower()

    def test_config_save_redirects_or_shows_success(self, client):
        """S1.7: Save valid config and verify success response."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry(),
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.save_config"
            ) as mock_save,
            patch(
                "app.platform.services.speech_runtime.SpeechRuntimeCoordinator.reload_after_config_save"
            ),
        ):
            response = client.post(
                "/config",
                data={
                    "llm_preset_id": "cloud",
                    "api_key": "test-key",
                    "timeout": "60",
                    "locale": "en",
                },
            )
        assert response.status_code == 200
        mock_save.assert_called_once()
        assert "saved" in response.text.lower() or "success" in response.text.lower()

    def test_after_save_setup_no_longer_redirects(self, client):
        """S1.8: After config saved, GET /setup returns setup page."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch(
                "app.interview.api.setup.list_tracks",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior"],
            ),
            patch(
                "app.interview.api.setup.list_categories",
                return_value=["basics"],
            ),
        ):
            response = client.get("/setup")
        assert response.status_code == 200
        assert "setup" in response.text.lower()

    def test_delete_config_then_setup_redirects(self, client):
        """S1.9: DELETE /config then GET /setup redirects to /config."""
        with (
            patch(
                "app.platform.services.config.ConfigService.delete_config"
            ) as mock_delete,
        ):
            response = client.delete("/config")
        assert response.status_code == 200
        mock_delete.assert_called_once()

        # After deletion, setup should redirect
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=None,
        ):
            response = client.get("/setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/config"
