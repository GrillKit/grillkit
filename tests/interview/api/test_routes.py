# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview HTTP routes (dashboard and legacy endpoints)."""

from unittest.mock import patch


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
