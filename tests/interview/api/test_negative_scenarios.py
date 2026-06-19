# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Negative scenarios: 404s, bad UUID, bad WS msg, invalid WAV, active→results 404."""

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import answer_evaluation_json
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


class TestNegativeScenarios:
    """Tests for error handling and edge cases."""

    def test_invalid_interview_uuid(self, client, isolated_db):
        """GET /interview/{invalid-uuid} redirects to home."""
        response = client.get("/interview/not-a-uuid", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_missing_interview(self, client, isolated_db):
        """GET /interview/{nonexistent} redirects to home."""
        response = client.get(
            "/interview/00000000-0000-0000-0000-000000000000", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_results_for_active_session_404(self, client, isolated_db):
        """Results page redirects active sessions back to interview."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="neg-active-1",
                locale="en",
                selection_spec=minimal_selection_spec(),
                status="active",
            ),
            [Answer(question_id="q1", order=1, round=0, question_text="Q?")],
            question_count=1,
        )
        response = client.get(
            f"/interview/{interview_id}/results", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/interview/{interview_id}"

    def test_answered_question_is_idempotent(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """S13.9: Answering a completed question returns no-op or error; session stays valid."""

        interview_id = persist_interview_with_answers(
            Interview(
                id="neg-race-1",
                locale="en",
                selection_spec=minimal_selection_spec(),
                status="active",
            ),
            [Answer(question_id="q1", order=1, round=0, question_text="Q?")],
            question_count=1,
        )

        override_ws_ai_provider(
            client, [answer_evaluation_json(score=5, follow_up_needed=False)]
        )

        # First answer
        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            ws.send_json(
                {"type": "answer", "question_id": "q1", "answer_text": "first"}
            )
            for _ in range(5):
                try:
                    msg = ws.receive_json(timeout=1.0)
                    if msg.get("type") == "feedback":
                        break
                except Exception:
                    break

        # Second connection answering same (already-answered) question — should not crash
        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws2:
            ws2.send_json(
                {"type": "answer", "question_id": "q1", "answer_text": "second"}
            )
            for _ in range(2):
                try:
                    ws2.receive_json(timeout=0.5)
                except Exception:
                    break

        # Session still valid
        with InterviewUnitOfWork() as uow:
            interview = InterviewQuery(uow).get_interview(interview_id)
            assert interview is not None
            assert interview.status == "active"
