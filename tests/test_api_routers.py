# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for API routers."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.config import ProviderConfig


@pytest.fixture
def client():
    """Create a test client with mocked database."""
    with patch("app.main.init_db"):
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


class TestRootRouter:
    """Tests for root router endpoints."""

    def test_root_endpoint_returns_html(self, client):
        """Test root endpoint returns HTML response."""
        with patch("app.api.root.ConfigService.get_config", return_value=None):
            response = client.get("/")
            # Should return HTML (200) or redirect
            assert response.status_code in [200, 307, 302]
            if response.status_code == 200:
                assert "text/html" in response.headers.get("content-type", "")

    def test_root_with_config(self, client):
        """Test root endpoint with configuration."""
        mock_config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="https://api.openai.com",
            model="gpt-4",
            api_key="test-key",
        )

        with patch("app.api.root.ConfigService.get_config", return_value=mock_config):
            response = client.get("/")
            # Should return HTML response
            assert response.status_code == 200


class TestConfigRouter:
    """Tests for config router endpoints."""

    def test_config_page_get(self, client):
        """Test GET /config endpoint returns HTML."""
        mock_config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="https://api.openai.com",
            model="gpt-4",
            api_key="test-key",
        )

        with patch("app.api.config.ConfigService.get_config", return_value=mock_config):
            with patch(
                "app.api.config.ProviderFactory.get_provider_types", return_value=[]
            ):
                response = client.get("/config")
                assert response.status_code == 200
                assert "text/html" in response.headers.get("content-type", "")

    def test_config_page_get_no_config(self, client):
        """Test GET /config without existing config."""
        with patch("app.api.config.ConfigService.get_config", return_value=None):
            with patch(
                "app.api.config.ProviderFactory.get_provider_types", return_value=[]
            ):
                response = client.get("/config")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_save_config_success(self, client):
        """Test POST /config with successful connection test."""
        with patch(
            "app.api.config.ConfigService.test_connection", return_value=(True, "OK")
        ):
            with patch("app.api.config.ConfigService.save_config") as mock_save:
                with patch(
                    "app.api.config.ProviderFactory.get_provider_types", return_value=[]
                ):
                    response = client.post(
                        "/config",
                        data={
                            "provider_type": "openai-compatible",
                            "base_url": "https://api.openai.com",
                            "model": "gpt-4",
                            "api_key": "test-key",
                            "timeout": 60.0,
                        },
                    )

                    assert response.status_code == 200
                    mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_config_failure(self, client):
        """Test POST /config with failed connection test."""
        with patch(
            "app.api.config.ConfigService.test_connection",
            return_value=(False, "Connection failed"),
        ):
            with patch(
                "app.api.config.ProviderFactory.get_provider_types", return_value=[]
            ):
                response = client.post(
                    "/config",
                    data={
                        "provider_type": "openai-compatible",
                        "base_url": "https://api.openai.com",
                        "model": "gpt-4",
                        "api_key": "test-key",
                        "timeout": 60.0,
                    },
                )

                assert response.status_code == 200

    def test_delete_config(self, client):
        """Test DELETE /config endpoint."""
        with patch("app.api.config.ConfigService.delete_config") as mock_delete:
            with patch(
                "app.api.config.ProviderFactory.get_provider_types", return_value=[]
            ):
                response = client.delete("/config")

                assert response.status_code == 200
                mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_config_success(self, client):
        """Test POST /config/test with successful connection."""
        with patch(
            "app.api.config.ConfigService.test_connection",
            return_value=(True, "Connection successful"),
        ):
            response = client.post(
                "/config/test",
                data={
                    "provider_type": "openai-compatible",
                    "base_url": "https://api.openai.com",
                    "model": "gpt-4",
                    "api_key": "test-key",
                    "timeout": 60.0,
                },
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_test_config_failure(self, client):
        """Test POST /config/test with failed connection."""
        with patch(
            "app.api.config.ConfigService.test_connection",
            return_value=(False, "Invalid API key"),
        ):
            response = client.post(
                "/config/test",
                data={
                    "provider_type": "openai-compatible",
                    "base_url": "https://api.openai.com",
                    "model": "gpt-4",
                    "api_key": "invalid-key",
                    "timeout": 60.0,
                },
            )

            assert response.status_code == 200
