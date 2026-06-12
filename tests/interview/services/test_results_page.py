# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SessionResultsPageService."""

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.results_page import SessionResultsPageService
from tests.helpers.completed_session_seed import seed_completed_theory_interview


def test_session_results_page_service_builds_section_cards(isolated_db) -> None:
    """Results hub includes enabled section cards with review links."""
    interview_id = seed_completed_theory_interview("results-hub-1")
    with InterviewUnitOfWork() as uow:
        interview = uow.interviews.get_read_model(interview_id)
    assert interview is not None
    context = SessionResultsPageService.build_context(interview)
    assert context is not None
    assert context.theory_review_url == f"/interview/{interview_id}/theory"
    assert len(context.section_cards) == 1
    assert context.section_cards[0].section == "theory"
