# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for API routers."""

import time
from typing import Any
from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app.ai.llm_models import LLMModelEntry
from app.main import create_app
from app.platform.services.config import ProviderConfig
from app.shared.domain.exceptions import InterviewNotActiveError, InterviewNotFoundError


async def _raising_answer_stream(
    exc: Exception,
    interview_id: str,
    question_id: str,
    answer_text: str,
    **kwargs: Any,
) -> None:
    raise exc
    yield  # type: ignore[misc, unreachable]


@pytest.fixture
def client():
    """Create a test client with mocked database."""
    from app.interview.api.deps import get_ai_provider
    from tests.fakes import FakeProvider

    async def _fake_ai_provider():
        yield FakeProvider([])

    with patch("app.main.init_db"):
        app = create_app()
        app.dependency_overrides[get_ai_provider] = _fake_ai_provider
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()


class MockInterview:
    """Minimal mock of Interview for WebSocket tests."""

    def __init__(self, status: str = "active"):
        self.id = "test-session-id"
        self.status = status
        self.answers = []
        self.question_count = 5
        self.locale = "en"
        self.selection_spec = (
            '{"version":1,"sources":[{"language":"python","level":"junior",'
            '"categories":["data-structures"]}]}'
        )
        self.score = None
        self.overall_feedback = None


class TestDashboardRouter:
    """Tests for the dashboard home page."""

    def test_dashboard_includes_interview_history(self, client):
        """Dashboard passes interview history to the template."""
        mock_rows = [
            type(
                "Row",
                (),
                {
                    "id": "id-1",
                    "title": "Python Interview",
                    "question_count": 5,
                    "score_display": "10 / 15",
                    "status": "completed",
                    "status_label": "Completed",
                    "datetime_display": "18 May 2026, 14:30",
                    "url": "/interview/id-1",
                },
            )(),
        ]
        with patch(
            "app.interview.services.dashboard.DashboardBuilder.list_rows",
            return_value=mock_rows,
        ):
            response = client.get("/")
            assert response.status_code == 200
            assert "Interview history" in response.text
            assert "Python Interview" in response.text

    def test_dashboard_returns_html(self, client):
        """Dashboard always returns HTML, even without provider config."""
        with patch(
            "app.interview.services.dashboard.DashboardBuilder.list_rows",
            return_value=[],
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Dashboard" in response.text


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
        mock_config = ProviderConfig(
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

    async def test_save_config_preserves_api_key_when_field_empty(self, client):
        """POST /config keeps the stored key when the password field is left blank."""
        existing = ProviderConfig(
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
                "app.platform.api.config.LLMCatalogService.normalize_model_id",
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
                "app.platform.api.config.LLMCatalogService.normalize_model_id",
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
                "app.platform.api.config.LLMCatalogService.normalize_model_id",
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
                "app.platform.api.config.LLMCatalogService.normalize_model_id",
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
                "app.platform.api.config.LLMCatalogService.normalize_model_id",
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


class TestInterviewHttpRoutes:
    """Tests for interview HTTP surface (page only; interaction is WebSocket)."""

    def test_legacy_post_answer_removed(self, client):
        """Legacy form POST answer endpoint is no longer registered."""
        response = client.post(
            "/interview/test-id/answer",
            data={"question_id": "q1", "answer_text": "text"},
        )
        assert response.status_code == 404

    def test_legacy_post_complete_removed(self, client):
        """Legacy form POST complete endpoint is no longer registered."""
        response = client.post("/interview/test-id/complete")
        assert response.status_code == 404


class TestInterviewWebSocket:
    """Tests for WebSocket interview endpoint."""

    def test_websocket_unknown_message(self, client):
        """Test WebSocket returns error for unknown message type."""
        with (
            patch("app.interview.services.query.InterviewQuery.get_interview"),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json({"type": "unknown_command"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown message type" in response["message"]

    def test_websocket_answer_success(self, client):
        """Test WebSocket answer submission invokes stream_answer_submission."""
        stream_calls: list[tuple[str, str, str]] = []

        async def mock_stream(
            interview_id: str,
            question_id: str,
            answer_text: str,
            **kwargs: Any,
        ) -> None:
            stream_calls.append((interview_id, question_id, answer_text))
            return
            yield  # type: ignore[misc, unreachable]

        with (
            patch(
                "app.interview.services.answer_processing.AnswerProcessingService.stream_answer_submission",
                side_effect=mock_stream,
            ),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json(
                {
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                }
            )
            for _ in range(100):
                if stream_calls:
                    break
                time.sleep(0.01)
            assert stream_calls == [("test-id", "ds-001", "My answer")]

    def test_websocket_answer_missing_fields(self, client):
        """Test WebSocket returns error when question_id or answer_text is missing."""
        with (
            patch("app.interview.services.query.InterviewQuery.get_interview"),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json({"type": "answer", "question_id": ""})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Both" in response["message"]

    def test_websocket_answer_completed_session(self, client):
        """Test WebSocket rejects answer on completed session."""
        with (
            patch(
                "app.interview.services.answer_processing.AnswerProcessingService.stream_answer_submission",
                side_effect=lambda *args, **kwargs: _raising_answer_stream(
                    InterviewNotActiveError("test-id"), *args, **kwargs
                ),
            ),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json(
                {
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "completed" in response["message"].lower()

    def test_websocket_answer_session_not_found(self, client):
        """Test WebSocket returns error when session is not found."""
        with (
            patch(
                "app.interview.services.answer_processing.AnswerProcessingService.stream_answer_submission",
                side_effect=lambda *args, **kwargs: _raising_answer_stream(
                    InterviewNotFoundError("test-id"), *args, **kwargs
                ),
            ),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json(
                {
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "not found" in response["message"].lower()

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong returns session status."""
        mock_session = MockInterview(status="active")

        with (
            patch(
                "app.interview.services.query.InterviewQuery.get_interview",
                return_value=mock_session,
            ),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"
            assert response["status"] == "active"

    def test_websocket_ping_completed_session(self, client):
        """Test ping returns completed status."""
        mock_session = MockInterview(status="completed")

        with (
            patch(
                "app.interview.services.query.InterviewQuery.get_interview",
                return_value=mock_session,
            ),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"
            assert response["status"] == "completed"

    def test_websocket_complete_success(self, client):
        """Test WebSocket complete message triggers session completion."""
        with (
            patch(
                "app.interview.services.completion.InterviewCompletionService.complete_interview",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_complete,
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json({"type": "complete"})
            for _ in range(100):
                if mock_complete.await_count:
                    break
                time.sleep(0.01)
            mock_complete.assert_awaited_once_with(
                interview_id="test-id",
                provider=ANY,
            )

    def test_websocket_answer_service_error(self, client):
        """Test WebSocket handles ValueError from service layer."""
        with (
            patch(
                "app.interview.services.answer_processing.AnswerProcessingService.stream_answer_submission",
                side_effect=lambda *args, **kwargs: _raising_answer_stream(
                    ValueError("Invalid question"), *args, **kwargs
                ),
            ),
            client.websocket_connect("/interview/test-id/ws") as ws,
        ):
            ws.send_json(
                {
                    "type": "answer",
                    "question_id": "ds-001",
                    "answer_text": "My answer",
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Invalid question" in response["message"]
