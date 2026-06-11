# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for canonical theory HTTP and WebSocket routes."""

from unittest.mock import patch

from tests.helpers.interview_seed import seed_two_question_interview


class TestTheoryCanonicalRoutes:
    """Theory section transport under /interview/{id}/theory/."""

    def test_theory_websocket_answer_success(self, client, isolated_db):
        """Canonical theory WebSocket path accepts answers."""
        interview_id = seed_two_question_interview("theory-ws-1")
        with patch(
            "app.theory.services.submission.TheorySubmissionService.stream_answer_submission",
        ) as mock_stream:
            from app.interview.services.events import AnswerSavedEvent, EvaluatingEvent

            async def _events(*_args, **_kwargs):
                yield AnswerSavedEvent()
                yield EvaluatingEvent()

            mock_stream.side_effect = _events

            with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
                ws.send_json(
                    {
                        "type": "answer",
                        "question_id": "q1",
                        "answer_text": "My answer.",
                    }
                )
                assert ws.receive_json() == {"type": "saved"}
                assert ws.receive_json() == {"type": "evaluating"}
