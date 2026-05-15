# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for API routers."""

from unittest.mock import AsyncMock, MagicMock, patch

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


class MockSession:
    """Minimal mock of InterviewSession for WebSocket tests."""

    def __init__(self, status: str = "active"):
        self.id = "test-session-id"
        self.status = status
        self.answers = []
        self.question_count = 5
        self.level = "junior"
        self.category = "data-structures"
        self.score = None
        self.overall_feedback = None


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
        ), patch("app.api.config.ConfigService.save_config") as mock_save, patch(
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
        ), patch(
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


class TestInterviewWebSocket:
    """Tests for WebSocket interview endpoint."""

    def test_websocket_unknown_message(self, client):
        """Test WebSocket returns error for unknown message type."""
        with (
            patch("app.api.interview.InterviewSessionService.get_session"),
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({"type": "unknown_command"})
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "Unknown message type" in response["message"]

    def test_websocket_answer_success(self, client):
        """Test WebSocket answer submission flow."""
        mock_session = MockSession(status="active")

        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=mock_session,
            ),
            patch(
                "app.api.interview.InterviewSessionService.process_answer_submission",
                new_callable=AsyncMock,
            ) as mock_process,
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                })
                # Should not raise — service is called, no response sent back
                # (response events are sent via ws_send callback internally)
                mock_process.assert_awaited_once_with(
                    session_id="test-id",
                    question_id="ds-001",
                    answer_text="My answer",
                    ws_send=mock_process.call_args.kwargs["ws_send"],
                )

    def test_websocket_answer_missing_fields(self, client):
        """Test WebSocket returns error when question_id or answer_text is missing."""
        with patch("app.api.interview.InterviewSessionService.get_session"):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({"type": "answer", "question_id": ""})
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "Both" in response["message"]

    def test_websocket_answer_completed_session(self, client):
        """Test WebSocket rejects answer on completed session."""
        mock_session = MockSession(status="completed")

        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=mock_session,
            ),
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                })
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "completed" in response["message"].lower()

    def test_websocket_answer_session_not_found(self, client):
        """Test WebSocket returns error when session is not found."""
        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=None,
            ),
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                })
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "not found" in response["message"].lower()

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong returns session status."""
        mock_session = MockSession(status="active")

        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=mock_session,
            ),
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({"type": "ping"})
                response = ws.receive_json()
                assert response["type"] == "pong"
                assert response["status"] == "active"

    def test_websocket_ping_completed_session(self, client):
        """Test ping returns completed status."""
        mock_session = MockSession(status="completed")

        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=mock_session,
            ),
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({"type": "ping"})
                response = ws.receive_json()
                assert response["type"] == "pong"
                assert response["status"] == "completed"

    def test_websocket_complete_success(self, client):
        """Test WebSocket complete message triggers session completion."""
        mock_session = MockSession(status="active")

        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=mock_session,
            ),
            patch(
                "app.api.interview.InterviewSessionService.process_session_completion",
                new_callable=AsyncMock,
            ) as mock_complete,
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({"type": "complete"})
                mock_complete.assert_awaited_once_with(
                    session_id="test-id",
                    ws_send=mock_complete.call_args.kwargs["ws_send"],
                )

    def test_websocket_answer_service_error(self, client):
        """Test WebSocket handles ValueError from service layer."""
        mock_session = MockSession(status="active")

        with (
            patch(
                "app.api.interview.InterviewSessionService.get_session",
                return_value=mock_session,
            ),
            patch(
                "app.api.interview.InterviewSessionService.process_answer_submission",
                new_callable=AsyncMock,
                side_effect=ValueError("Invalid question"),
            ),
        ):
            with client.websocket_connect("/interview/test-id/ws") as ws:
                ws.send_json({
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                })
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "Invalid question" in response["message"]
