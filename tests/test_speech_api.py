# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for speech model API endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.services.config import ProviderConfig
from app.services.whisper_model import WhisperModelService
from app.services.whisper_runtime import WhisperRuntime


@pytest.fixture
def client():
    """Create a test client with mocked database init."""
    with patch("app.main.init_db"):
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture(autouse=True)
def reset_download_state():
    """Reset in-memory download state between tests."""
    WhisperRuntime.unload()
    WhisperModelService._active_size = None
    WhisperModelService._percent = 0
    WhisperModelService._error_size = None
    WhisperModelService._error_message = None
    yield


class TestSpeechModelApi:
    """Tests for /speech/model/* routes."""

    def test_status_requires_config(self, client):
        """Status endpoint returns 400 without saved provider config."""
        with patch("app.services.config.ConfigService.get_config", return_value=None):
            response = client.get(
                "/speech/model/status",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 400

    def test_status_json_missing_model(self, client):
        """Status reports missing when no model is on disk."""
        mock_config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            speech_model_size="small",
        )
        with (
            patch(
                "app.services.config.ConfigService.get_config", return_value=mock_config
            ),
            patch("app.services.whisper_model.is_installed", return_value=False),
        ):
            response = client.get(
                "/speech/model/status",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "missing"
        assert payload["size"] == "small"

    def test_download_schedules_work(self, client):
        """Download endpoint returns downloading state for HTML clients."""
        mock_config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="ru",
            speech_model_size="small",
        )
        with (
            patch(
                "app.services.config.ConfigService.get_config", return_value=mock_config
            ),
            patch("app.services.whisper_model.is_installed", return_value=False),
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
