# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for speech model API endpoints."""

from unittest.mock import patch

import pytest

from app.platform.services.config import AppConfig
from app.speech.services.whisper_model import WhisperModelService
from app.speech.services.whisper_runtime import WhisperRuntime


@pytest.fixture(autouse=True)
def reset_download_state():
    """Reset in-memory download state between tests."""
    WhisperRuntime.unload()
    WhisperModelService.reset_download_state()
    yield


class TestSpeechModelApi:
    """Tests for /speech/model/* routes."""

    def test_status_without_config_uses_defaults(self, client):
        """Status endpoint falls back to default size when config is unset."""
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch("app.speech.services.whisper_model.is_installed", return_value=False),
        ):
            response = client.get(
                "/speech/model/status",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "missing"
        assert payload["size"] == "small"

    def test_status_without_config_accepts_size_query(self, client):
        """Status endpoint honors size query param before config is saved."""
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch("app.speech.services.whisper_model.is_installed", return_value=False),
        ):
            response = client.get(
                "/speech/model/status?size=medium",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        assert response.json()["size"] == "medium"

    def test_status_query_overrides_saved_config(self, client):
        """Status endpoint honors size query param over saved config on Configuration."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            speech_model_size="small",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch("app.speech.services.whisper_model.is_installed", return_value=False),
        ):
            response = client.get(
                "/speech/model/status?size=medium&locale=ru",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["size"] == "medium"
        assert payload["locale"] == "ru"

    def test_status_json_missing_model(self, client):
        """Status reports missing when no model is on disk."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            speech_model_size="small",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch("app.speech.services.whisper_model.is_installed", return_value=False),
        ):
            response = client.get(
                "/speech/model/status",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "missing"
        assert payload["size"] == "small"

    def test_download_without_config_uses_defaults(self, client):
        """Download endpoint schedules work before provider config is saved."""
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch("app.speech.services.whisper_model.is_installed", return_value=False),
            patch.object(
                WhisperModelService,
                "_run_download",
                side_effect=lambda _size: None,
            ),
        ):
            response = client.post(
                "/speech/model/download",
                headers={"Accept": "text/html"},
            )
        assert response.status_code == 200
        assert "speech-model-status" in response.text

    def test_download_schedules_work(self, client):
        """Download endpoint returns downloading state for HTML clients."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="ru",
            speech_model_size="small",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch("app.speech.services.whisper_model.is_installed", return_value=False),
            patch.object(
                WhisperModelService,
                "_run_download",
                side_effect=lambda _size: None,
            ),
        ):
            response = client.post(
                "/speech/model/download",
                headers={"Accept": "text/html"},
            )
        assert response.status_code == 200
        assert "speech-model-status" in response.text

    def test_options_lists_sizes(self, client):
        """Options endpoint returns all configured speech model sizes."""
        response = client.get("/speech/model/options")
        assert response.status_code == 200
        sizes = {item["size"] for item in response.json()["options"]}
        assert sizes == {"small", "medium", "large"}
