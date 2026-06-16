# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding section page context."""

import asyncio
import json

from app.coding.services.page import CodingPageService
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.page import SessionPageService
from tests.helpers.coding_seed import seed_active_coding_interview


def test_build_context_returns_none_without_section(isolated_db):
    """Coding page context is absent when the session has no coding section."""
    del isolated_db
    assert CodingPageService.build_context_for("missing-session") is None


def test_build_context_exposes_current_task(isolated_db):
    """Coding page context includes the active task and progress fields."""
    interview_id, task_id = seed_active_coding_interview("coding-page-1")
    context = CodingPageService.build_context_for(interview_id)
    assert context is not None
    assert context.task_count == 1
    assert context.completed_tasks == 0
    assert context.current_task is not None
    assert context.current_task["task_id"] == task_id
    assert context.current_task_row_id is not None
    assert "hidden_tests" not in json.dumps(context.current_task["task_spec"])


def test_full_template_context_includes_coding_key(isolated_db):
    """Session page merges coding context for interview.html."""
    interview_id, _task_id = seed_active_coding_interview("coding-page-2")
    from app.interview.services.query import InterviewQuery

    interview = InterviewQuery.load(interview_id)
    assert interview is not None
    with InterviewUnitOfWork() as uow:
        template_context = asyncio.run(
            SessionPageService(uow).build_full_template_context(
                interview,
                config=None,
            )
        )
    assert template_context["coding"] is not None
    assert template_context["coding"]["task_count"] == 1
    assert template_context["session_mode_label"]


def test_interview_route_uses_coding_template(client, isolated_db):
    """Active coding phase renders the dedicated coding interview template."""
    interview_id, _task_id = seed_active_coding_interview("coding-template-1")
    response = client.get(f"/interview/{interview_id}")
    assert response.status_code == 200
    assert "coding-session" in response.text
    assert "coding-session__assignment" in response.text
    assert "I know this" in response.text
    assert "interview-chat-panel" not in response.text
