# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for FastAPI application factory."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, lifespan


class TestCreateApp:
    """Tests for create_app factory function."""

    def test_app_creation(self):
        """Test that create_app returns a FastAPI instance."""
        app = create_app()
        assert app is not None
        assert app.title == "GrillKit"
        assert app.description == "AI Interview Trainer"
        assert app.version == "0.1.0"

    def test_static_files_mounted(self):
        """Test that static files are mounted."""
        app = create_app()
        # Check that static route is mounted
        routes = [route.path for route in app.routes]
        assert any("/static" in route for route in routes)

    def test_routers_included(self):
        """Test that routers are included."""
        app = create_app()
        routes = [route.path for route in app.routes]

        # Check root router paths exist
        assert "/" in routes or "/" in [r.path for r in app.routes]
        # Check config router paths exist (they have /config prefix)
        config_routes = [
            r for r in app.routes if hasattr(r, "path") and "/config" in r.path
        ]
        assert len(config_routes) > 0


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_calls_init_db(self):
        """Test that lifespan calls init_db on startup."""
        with patch("app.main.init_db") as mock_init_db:
            mock_app = MagicMock()

            async with lifespan(mock_app):
                pass

            mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_yields_control(self):
        """Test that lifespan yields control to the app."""
        with patch("app.main.init_db"):
            mock_app = MagicMock()
            entered = False
            exited = False

            async with lifespan(mock_app):
                entered = True

            exited = True
            assert entered
            assert exited


class TestAppIntegration:
    """Integration tests for the application."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        with patch("app.main.init_db"):
            app = create_app()
            with TestClient(app) as test_client:
                yield test_client

    def test_root_endpoint(self, client):
        """Test that root endpoint returns HTML."""
        response = client.get("/")
        # Should return 200 or redirect
        assert response.status_code in [200, 307, 302]

    def test_config_page_exists(self, client):
        """Test that config page endpoint exists."""
        response = client.get("/config")
        # Should return 200 or redirect
        assert response.status_code in [200, 307, 302]
