# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SessionResultsPageService."""

from app.interview.queries.projection import load_interview_read
from app.interview.queries.results_page import (
    CompletedSessionResults as SessionResultsPageService,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from tests.helpers.completed_session_seed import seed_completed_theory_interview


def test_session_results_page_service_builds_section_cards(isolated_db) -> None:
    """Results hub includes enabled section cards with review links."""
    interview_id = seed_completed_theory_interview("results-hub-1")
    with InterviewUnitOfWork() as uow:
        interview = load_interview_read(uow, interview_id)
        assert interview is not None
        context = SessionResultsPageService(uow).build_context(interview)
    assert context is not None
    assert context.theory_review_url == f"/interview/{interview_id}/theory"
    assert len(context.section_cards) == 1
    assert context.section_cards[0].section == "theory"
