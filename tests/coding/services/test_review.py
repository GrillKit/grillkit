# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for CodingReviewService."""

import json

from app.coding.services.review import CodingReviewService
from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import CodingTask
from tests.helpers.completed_session_seed import seed_completed_coding_interview


def test_coding_review_service_groups_task_rounds(isolated_db) -> None:
    """Coding review groups submitted rounds on one page."""
    interview_id = seed_completed_coding_interview()
    with InterviewUnitOfWork(auto_commit=True) as uow:
        section = uow.coding_sections.get_aggregate(interview_id)
        assert section is not None
        follow_up = CodingTask(
            coding_section_id=section.id,
            task_id="cod-001",
            order=1,
            round=1,
            prompt_text="Explain your approach.",
            task_spec=json.dumps({"language": "python"}),
            submitted_code="I used a direct return.",
            score=3,
            feedback="Explanation was brief.",
        )
        uow.session.add(follow_up)

    with InterviewUnitOfWork() as uow:
        context = CodingReviewService(uow).build_context_for(interview_id)
    assert context is not None
    assert len(context.tasks) == 1
    assert len(context.tasks[0].rounds) == 2
    assert context.tasks[0].total_score == 7


def test_coding_review_page_renders_task_accordion(client, isolated_db) -> None:
    """Coding review page renders per-task accordion with final submit."""
    interview_id = seed_completed_coding_interview("results-coding-page-1")
    response = client.get(f"/interview/{interview_id}/coding")
    assert response.status_code == 200
    assert "Coding Tasks" in response.text
    assert "cod-001" in response.text
    assert "Works for the sample case." in response.text
