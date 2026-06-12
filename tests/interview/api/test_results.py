# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for completed session results HTTP routes."""

from tests.helpers.completed_session_seed import seed_completed_theory_interview


def test_completed_interview_page_redirects_to_results(client, isolated_db) -> None:
    """Completed sessions no longer render the active interview page."""
    interview_id = seed_completed_theory_interview("results-redirect-1")
    response = client.get(f"/interview/{interview_id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/interview/{interview_id}/results"


def test_results_page_renders_for_completed_session(client, isolated_db) -> None:
    """Results hub renders overall feedback and section cards."""
    interview_id = seed_completed_theory_interview("results-page-1")
    response = client.get(f"/interview/{interview_id}/results")
    assert response.status_code == 200
    assert "Overall Evaluation" in response.text
    assert "View details" in response.text
    assert "Good theory performance." in response.text
