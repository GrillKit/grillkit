# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for theory WebSocket route handlers."""

import time
from typing import Any
from unittest.mock import ANY, AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app.interview.domain.exceptions import (
    InterviewNotActiveError,
    InterviewNotFoundError,
)
from app.main import create_app


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
    """Create a test client with mocked database and fake AI provider."""
    from app.interview.api.deps import get_ai_provider
    from tests.fakes import FakeProvider

    async def _fake_ai_provider():
        yield FakeProvider([])

    with (
        patch("app.main.run_migrations"),
        patch(
            "app.platform.services.speech_runtime.SpeechRuntimeCoordinator.startup",
            new=AsyncMock(),
        ),
        patch(
            "app.platform.services.speech_runtime.SpeechRuntimeCoordinator.unload_all",
        ),
    ):
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
            '{"sources":[{"track":"python","level":"junior",'
            '"categories":["data-structures"]}]}'
        )
        self.score = None
        self.overall_feedback = None


class TestTheoryWebSocket:
    """Tests for theory WebSocket endpoint."""

    def test_websocket_unknown_message(self, client):
        """Test WebSocket returns error for unknown message type."""
        with (
            patch("app.interview.services.query.InterviewQuery.get_interview"),
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
                "app.theory.services.submission.TheorySubmissionService.stream_answer_submission",
                side_effect=mock_stream,
            ),
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
        ):
            ws.send_json({"type": "answer", "question_id": ""})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Both" in response["message"]

    def test_websocket_answer_completed_session(self, client):
        """Test WebSocket rejects answer on completed session."""
        with (
            patch(
                "app.theory.services.submission.TheorySubmissionService.stream_answer_submission",
                side_effect=lambda *args, **kwargs: _raising_answer_stream(
                    InterviewNotActiveError("test-id"), *args, **kwargs
                ),
            ),
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
                "app.theory.services.submission.TheorySubmissionService.stream_answer_submission",
                side_effect=lambda *args, **kwargs: _raising_answer_stream(
                    InterviewNotFoundError("test-id"), *args, **kwargs
                ),
            ),
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
        ):
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"
            assert response["status"] == "completed"

    def test_websocket_complete_success(self, client):
        """Test WebSocket complete message triggers session completion."""
        with (
            patch(
                "app.interview.services.completion.SessionCompletionService.complete_session",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_complete,
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
                "app.theory.services.submission.TheorySubmissionService.stream_answer_submission",
                side_effect=lambda *args, **kwargs: _raising_answer_stream(
                    ValueError("Invalid question"), *args, **kwargs
                ),
            ),
            client.websocket_connect("/interview/test-id/theory/ws") as ws,
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
