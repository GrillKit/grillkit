# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheoryReviewService."""

from app.theory.services.review import TheoryReviewService
from tests.helpers.completed_session_seed import seed_completed_theory_interview


def test_theory_review_service_builds_chat_history(isolated_db) -> None:
    """Theory review exposes answered rounds and fallback section feedback."""
    interview_id = seed_completed_theory_interview()
    context = TheoryReviewService.build_context(interview_id)
    assert context is not None
    assert len(context.answers) == 1
    assert context.answers[0].feedback == "Clear and concise."
    assert "Clear and concise." in context.section_feedback["section_feedback"]


def test_theory_review_page_renders_history(client, isolated_db) -> None:
    """Theory review page renders chat history and section feedback."""
    interview_id = seed_completed_theory_interview("results-theory-page-1")
    response = client.get(f"/interview/{interview_id}/theory")
    assert response.status_code == 200
    assert "Conversation History" in response.text
    assert "A programming language" in response.text
    assert "Clear and concise." in response.text
