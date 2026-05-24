# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview completion persistence."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.completion import InterviewCompletionService
from app.interview.services.evaluator.service import InterviewEvaluation
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import FakeProvider
from tests.helpers.selection import minimal_selection_spec


@pytest.mark.asyncio
async def test_complete_interview_persists_completed_status(isolated_db):
    """After completion, interview is stored as completed with score and time."""
    interview_id = "completion-persist-1"

    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            question_count=1,
            question_ids=json.dumps(["q1"]),
            status="active",
        )
        uow.interviews.add(interview)
        answer = Answer(
            interview_id=interview_id,
            question_id="q1",
            order=1,
            round=0,
            question_text="What is Python?",
        )
        answer.answer_text = "A programming language"
        answer.score = 5
        uow.answers.add(answer)

    mock_eval = InterviewEvaluation(
        overall_feedback="Good work",
        strengths_summary=["Clear answer"],
        topics_to_review=[],
        score_breakdown={"q1": {"score": 99, "max": 999}},
    )

    with patch(
        "app.interview.services.completion.InterviewEvaluatorService.evaluate_interview",
        new_callable=AsyncMock,
        return_value=mock_eval,
    ):
        events = await InterviewCompletionService.complete_interview(
            interview_id,
            provider=FakeProvider([]),
        )

    assert len(events) == 2

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert reloaded.score == 5
    assert reloaded.completed_at is not None
    assert reloaded.overall_feedback is not None
    stored = json.loads(reloaded.overall_feedback)
    assert stored["score_breakdown"]["q1"]["score"] == 5
    assert stored["score_breakdown"]["q1"]["max"] == 5
