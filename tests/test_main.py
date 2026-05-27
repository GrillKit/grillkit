# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for FastAPI application factory."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app, lifespan


class TestCreateApp:
    """Tests for create_app factory function."""

    def test_app_creation(self):
        """Test that create_app returns a FastAPI instance."""
        app = create_app()
        assert app is not None
        assert app.title == "GrillKit"
        assert app.description == "AI Interview Trainer"
        assert app.version == "2026.5.24"

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

        # Check dashboard home path exists
        assert "/" in routes or "/" in [r.path for r in app.routes]
        # Check config router paths exist (they have /config prefix)
        config_routes = [
            r for r in app.routes if hasattr(r, "path") and "/config" in r.path
        ]
        assert len(config_routes) > 0


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_calls_run_migrations(self):
        """Test that lifespan runs database migrations on startup."""
        with patch("app.main.run_migrations") as mock_run_migrations:
            mock_app = MagicMock()

            async with lifespan(mock_app):
                pass

            mock_run_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_yields_control(self):
        """Test that lifespan yields control to the app."""
        with patch("app.main.run_migrations"):
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
        with patch("app.main.run_migrations"):
            app = create_app()
            with TestClient(app) as test_client:
                yield test_client

    def test_dashboard_endpoint(self, client):
        """Test that the home page returns the dashboard HTML."""
        with patch(
            "app.interview.services.dashboard.DashboardBuilder.list_rows",
            return_value=[],
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_config_page_exists(self, client):
        """Test that config page endpoint exists."""
        response = client.get("/config")
        # Should return 200 or redirect
        assert response.status_code in [200, 307, 302]
