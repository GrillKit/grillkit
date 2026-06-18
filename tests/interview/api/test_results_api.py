# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Results & review API tests."""

from app.shared.infrastructure.models import Answer, Interview
from tests.helpers.completed_session_seed import (
    seed_completed_coding_interview,
    seed_completed_theory_interview,
)
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


class TestResultsApi:
    """Tests for completed session results endpoints."""

    def test_results_renders_for_completed_theory(self, client, isolated_db):
        """GET /results shows evaluation for completed theory session."""
        interview_id = seed_completed_theory_interview("results-t-1")
        response = client.get(f"/interview/{interview_id}/results")
        assert response.status_code == 200
        assert "Overall Evaluation" in response.text
        assert "Good theory performance." in response.text

    def test_results_renders_for_completed_coding(self, client, isolated_db):
        """GET /results shows evaluation for completed coding session."""
        interview_id = seed_completed_coding_interview("results-c-1")
        response = client.get(f"/interview/{interview_id}/results")
        assert response.status_code == 200
        assert "Good coding performance." in response.text

    def test_theory_review_shows_chat_history(self, client, isolated_db):
        """GET /theory shows full Q&A history for completed sessions."""
        interview_id = seed_completed_theory_interview("review-t-1")
        response = client.get(f"/interview/{interview_id}/theory")
        assert response.status_code == 200
        assert "What is Python?" in response.text
        assert "A programming language" in response.text

    def test_coding_review_shows_tasks_and_code(self, client, isolated_db):
        """GET /coding shows per-task accordion with code."""
        interview_id = seed_completed_coding_interview("review-c-1")
        response = client.get(f"/interview/{interview_id}/coding")
        assert response.status_code == 200
        assert "def solve()" in response.text

    def test_theory_review_active_session_redirects(self, client, isolated_db):
        """Theory review for active sessions redirects to results."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="review-active-1",
                locale="en",
                selection_spec=minimal_selection_spec(),
                status="active",
            ),
            [Answer(question_id="q1", order=1, round=0, question_text="Q?")],
            question_count=1,
        )
        response = client.get(f"/interview/{interview_id}/theory", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/interview/{interview_id}/results"

    def test_coding_review_active_session_redirects(self, client, isolated_db):
        """Coding review for active sessions redirects to results."""
        from tests.helpers.coding_seed import seed_active_coding_interview
        interview_id, _ = seed_active_coding_interview("review-active-c")
        response = client.get(f"/interview/{interview_id}/coding", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/interview/{interview_id}/results"
