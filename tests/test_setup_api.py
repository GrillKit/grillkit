# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for setup API cascaded options."""

from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.platform.services.config import ProviderConfig


@pytest.fixture
def client():
    """Create a test client with mocked database init."""
    with patch("app.main.init_db"):
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


class TestSetupOptions:
    """Tests for GET /setup/options."""

    def test_lists_languages(self, client):
        """Options without params returns available programming languages."""
        with patch(
            "app.interview.api.setup.list_languages",
            return_value=["database", "python"],
        ):
            response = client.get("/setup/options")
        assert response.status_code == 200
        assert response.json() == {"languages": ["database", "python"]}

    def test_lists_levels_for_language(self, client):
        """Options with language returns levels for that language."""
        with (
            patch(
                "app.interview.api.setup.list_languages",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior", "middle"],
            ),
        ):
            response = client.get("/setup/options", params={"language": "python"})
        assert response.status_code == 200
        assert response.json() == {"levels": ["junior", "middle"]}

    def test_lists_categories_for_language_and_level(self, client):
        """Options with language and level returns topic categories."""
        with (
            patch(
                "app.interview.api.setup.list_languages",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior"],
            ),
            patch(
                "app.interview.api.setup.list_categories",
                return_value=["basics", "oop"],
            ),
        ):
            response = client.get(
                "/setup/options",
                params={"language": "python", "level": "junior"},
            )
        assert response.status_code == 200
        assert response.json() == {"categories": ["basics", "oop"]}

    def test_unknown_language_returns_404(self, client):
        """Unknown language slug returns 404."""
        with patch(
            "app.interview.api.setup.list_languages",
            return_value=["python"],
        ):
            response = client.get("/setup/options", params={"language": "java"})
        assert response.status_code == 404


class TestSetupConfigRedirect:
    """Setup requires provider configuration before starting an interview."""

    def test_setup_get_redirects_without_config(self, client):
        """GET /setup redirects to /config when provider is not configured."""
        with patch("app.platform.services.config.ConfigService.get_config", return_value=None):
            response = client.get("/setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/config"

    def test_setup_post_redirects_without_config(self, client):
        """POST /setup redirects to /config when provider is not configured."""
        with patch("app.platform.services.config.ConfigService.get_config", return_value=None):
            response = client.post(
                "/setup",
                data={
                    "language": "python",
                    "topic": "basics",
                    "level": "junior",
                    "question_count": "5",
                },
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert response.headers["location"] == "/config"

    def test_setup_get_shows_configured_locale(self, client):
        """GET /setup displays interview language from saved config."""
        mock_config = ProviderConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="ru",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config", return_value=mock_config
            ),
            patch("app.interview.api.setup.list_languages", return_value=["python"]),
            patch("app.interview.api.setup.list_levels", return_value=["junior"]),
            patch("app.interview.api.setup.list_categories", return_value=["basics"]),
        ):
            response = client.get("/setup")
        assert response.status_code == 200
        assert "Russian" in response.text
        assert 'name="locale"' not in response.text
