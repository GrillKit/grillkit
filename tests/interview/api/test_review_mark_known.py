# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Review mark-as-known integration tests."""

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.known_questions import KnownQuestionsService
from tests.helpers.completed_session_seed import seed_completed_theory_interview


class TestReviewMarkKnown:
    """Mark known from theory and coding review pages."""

    def test_mark_known_from_theory_review(self, client, isolated_db):
        """POST adds theory question to known list."""
        seed_completed_theory_interview("mark-theory-1")
        response = client.post(
            "/known-questions",
            json={"branch": "theory", "item_id": "q-mark-1"},
        )
        assert response.status_code == 200
        known = client.get("/known-questions").json()
        assert "q-mark-1" in known.get("theory", [])

    def test_mark_known_from_coding_review(self, client, isolated_db):
        """POST adds coding task to known list."""
        response = client.post(
            "/known-questions",
            json={"branch": "coding", "item_id": "cod-mark-1"},
        )
        assert response.status_code == 200
        known = client.get("/known-questions").json()
        assert "cod-mark-1" in known.get("coding", [])

    def test_remove_known_question(self, client, isolated_db):
        """DELETE removes item from known list."""
        client.post("/known-questions", json={"branch": "theory", "item_id": "q-rm-1"})
        response = client.request(
            "DELETE",
            "/known-questions",
            json={"branch": "theory", "item_id": "q-rm-1"},
        )
        assert response.status_code == 200
        known = client.get("/known-questions").json()
        assert "q-rm-1" not in known.get("theory", [])

    def test_known_questions_manage_page(self, client, isolated_db):
        """GET /manage renders HTML table with known questions."""
        with InterviewUnitOfWork(auto_commit=True) as uow:
            KnownQuestionsService(uow).mark_known("theory", "q-manage-1")
        response = client.get("/known-questions/manage")
        assert response.status_code == 200
        assert "q-manage-1" in response.text
