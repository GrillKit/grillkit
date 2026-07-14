# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview completion persistence."""

from unittest.mock import AsyncMock, patch

import pytest

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.completion import SessionCompletionService
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from app.theory.services.evaluator.models import InterviewEvaluation
from tests.fakes import FakeProvider
from tests.helpers.coding_seed import seed_active_coding_interview
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


async def _complete_session(interview_id: str, provider: FakeProvider):
    """Run session completion inside an auto-commit application UoW."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = SessionCompletionService(uow)
        return await service.complete_session(interview_id, provider)


@pytest.mark.asyncio
async def test_complete_interview_persists_completed_status(isolated_db):
    """After completion, interview is stored as completed with score and time."""
    interview_id = "completion-persist-1"

    persist_interview_with_answers(
        Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            Answer(
                question_id="q1",
                order=1,
                round=0,
                question_text="What is Python?",
                answer_text="A programming language",
                score=5,
            )
        ],
    )

    mock_eval = InterviewEvaluation(
        overall_feedback="Good work",
        strengths_summary=["Clear answer"],
        topics_to_review=[],
        score_breakdown={
            "theory": {
                "score": 99,
                "max": 999,
                "skipped": False,
                "questions": {"q1": {"score": 99, "max": 999}},
            }
        },
    )

    with patch(
        "app.interview.services.completion.SessionEvaluatorService.evaluate_session",
        new_callable=AsyncMock,
        return_value=mock_eval,
    ):
        events = await _complete_session(
            interview_id,
            FakeProvider([]),
        )

    assert len(events) == 2

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert reloaded.score == 5
    assert reloaded.completed_at is not None
    assert reloaded.overall_feedback is not None
    theory_breakdown = reloaded.overall_feedback["score_breakdown"]["theory"]
    assert theory_breakdown["questions"]["q1"]["score"] == 5
    assert theory_breakdown["questions"]["q1"]["max"] == 5


@pytest.mark.asyncio
async def test_complete_coding_only_session_includes_coding_breakdown(isolated_db):
    """Completion merges coding section scores into the session breakdown."""
    interview_id, _task_id = seed_active_coding_interview("coding-completion-1")
    with InterviewUnitOfWork(auto_commit=True) as uow:
        section = uow.coding_sections.get_aggregate(interview_id)
        assert section is not None
        task = section.find_first_unsubmitted()
        assert task is not None
        submitted = section.with_submit_test_summary(
            task.id,
            {"status": "success"},
            source_code="def solve():\n    return 1",
        )
        evaluated = submitted.with_evaluation(
            task.task_id,
            task.round,
            score=4,
            feedback="Good solution.",
        )
        uow.coding_sections.save_aggregate(evaluated)

    mock_eval = InterviewEvaluation(
        overall_feedback="Solid coding work",
        strengths_summary=["Clean code"],
        topics_to_review=[],
        score_breakdown={},
    )

    with patch(
        "app.interview.services.completion.SessionEvaluatorService.evaluate_session",
        new_callable=AsyncMock,
        return_value=mock_eval,
    ):
        events = await _complete_session(
            interview_id,
            FakeProvider([]),
        )

    assert len(events) == 2
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert reloaded.score == 4
    coding_breakdown = reloaded.overall_feedback["score_breakdown"]["coding"]
    assert coding_breakdown["score"] == 4
    assert coding_breakdown["questions"]["cod-001"]["score"] == 4


@pytest.mark.asyncio
async def test_complete_session_preserves_partial_theory_scores(isolated_db):
    """Early completion keeps earned points when not every theory task is answered."""
    interview_id = "completion-partial-theory-1"

    persist_interview_with_answers(
        Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            Answer(
                question_id="q1",
                order=1,
                round=0,
                question_text="What is Python?",
                answer_text="A programming language",
                score=4,
            ),
            Answer(
                question_id="q2",
                order=2,
                round=0,
                question_text="What is a list?",
            ),
            Answer(
                question_id="q3",
                order=3,
                round=0,
                question_text="What is a dict?",
            ),
        ],
        question_count=3,
    )

    mock_eval = InterviewEvaluation(
        overall_feedback="Partial session",
        strengths_summary=[],
        topics_to_review=[],
        score_breakdown={},
    )

    with patch(
        "app.interview.services.completion.SessionEvaluatorService.evaluate_session",
        new_callable=AsyncMock,
        return_value=mock_eval,
    ):
        events = await _complete_session(
            interview_id,
            FakeProvider([]),
        )

    assert len(events) == 2
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert reloaded.score == 4

    theory_breakdown = reloaded.overall_feedback["score_breakdown"]["theory"]
    assert theory_breakdown["skipped"] is True
    assert theory_breakdown["score"] == 4
    assert theory_breakdown["max"] == 5
    assert theory_breakdown["questions"]["q1"]["score"] == 4
