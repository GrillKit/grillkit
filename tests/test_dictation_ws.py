# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview dictation WebSocket."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.speech.services.dictation import DictationSession


@pytest.fixture
def client():
    """Create a test client without loading Whisper on startup."""
    with (
        patch("app.main.init_db"),
        patch(
            "app.speech.services.whisper_runtime.WhisperRuntime.load_size",
            return_value=False,
        ),
    ):
        app = create_app()
        app.state.speech_transcriber = None
        with TestClient(app) as test_client:
            yield test_client


def _active_interview():
    """Build a minimal active interview ORM-like object."""
    interview = MagicMock()
    interview.id = "test-session"
    interview.status = "active"
    interview.locale = "en"
    return interview


class TestDictationWebSocket:
    """Tests for WS /interview/{id}/dictation."""

    def test_rejects_when_model_not_loaded(self, client):
        """Connection closes with error when speech_transcriber is absent."""
        with (
            patch(
                "app.interview.services.query.InterviewQuery.get_interview",
                return_value=_active_interview(),
            ),
            client.websocket_connect("/interview/test-session/dictation") as ws,
        ):
            data = ws.receive_json()
        assert data["type"] == "error"
        assert "not loaded" in data["message"].lower()

    def test_start_stop_returns_final_text(self, client):
        """start → PCM → stop yields ready and final messages."""
        mock_transcriber = object()
        mock_session = MagicMock(spec=DictationSession)
        mock_session.finalize = AsyncMock(return_value="hello world")

        with (
            patch(
                "app.interview.services.query.InterviewQuery.get_interview",
                return_value=_active_interview(),
            ),
            patch(
                "app.speech.api.dictation.DictationSession", return_value=mock_session
            ),
        ):
            client.app.state.speech_transcriber = mock_transcriber
            with client.websocket_connect("/interview/test-session/dictation") as ws:
                ws.send_json({"type": "start"})
                assert ws.receive_json() == {"type": "ready"}
                ws.send_bytes(b"\x00\x00" * 50)
                ws.send_json({"type": "stop"})
                final = ws.receive_json()
                assert final == {"type": "final", "text": "hello world"}
                mock_session.append_pcm.assert_called()
                mock_session.finalize.assert_awaited_once_with(mock_transcriber, "en")

    def test_rejects_completed_interview(self, client):
        """Completed interviews receive an error and close."""
        interview = _active_interview()
        interview.status = "completed"
        with (
            patch(
                "app.interview.services.query.InterviewQuery.get_interview",
                return_value=interview,
            ),
            client.websocket_connect("/interview/test-session/dictation") as ws,
        ):
            data = ws.receive_json()
        assert data["type"] == "error"
        assert "not active" in data["message"].lower()
