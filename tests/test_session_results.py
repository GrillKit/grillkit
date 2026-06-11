# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for completed session results and section review pages."""

import json

import pytest

from app.coding.services.evaluator.service import CodingEvaluatorService
from app.coding.services.review import CodingReviewService
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.results_page import SessionResultsPageService
from app.shared.infrastructure.models import Answer, CodingTask, Interview
from app.theory.services.review import TheoryReviewService
from tests.fakes import FakeProvider, section_evaluation_json
from tests.helpers.coding_seed import (
    attach_coding_tasks,
    create_coding_section_for_interview,
)
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


def _seed_completed_theory_interview(interview_id: str = "results-theory-1") -> str:
    """Persist a completed theory interview with one answered question.

    Args:
        interview_id: Interview primary key.

    Returns:
        Interview UUID.
    """
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
                feedback="Clear and concise.",
            )
        ],
    )
    overall_feedback = {
        "overall_feedback": "Good theory performance.",
        "strengths_summary": ["basics"],
        "topics_to_review": [],
        "score_breakdown": {
            "theory": {
                "score": 4,
                "max": 5,
                "skipped": False,
                "questions": {"q1": {"score": 4, "max": 5}},
            }
        },
    }
    with InterviewUnitOfWork(auto_commit=True) as uow:
        aggregate = uow.interviews.get_aggregate(interview_id)
        assert aggregate is not None
        completed = aggregate.with_session_completed(overall_feedback)
        uow.interviews.save_aggregate(completed)
    return interview_id


def _seed_completed_coding_interview(interview_id: str = "results-coding-1") -> str:
    """Persist a completed coding-only interview with one submitted task.

    Args:
        interview_id: Interview primary key.

    Returns:
        Interview UUID.
    """
    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            locale="en",
            selection_spec=json.dumps(
                {
                    "version": 2,
                    "session_mode": "coding_only",
                    "theory": {"enabled": False},
                    "coding": {"enabled": True},
                }
            ),
            session_mode="coding_only",
            status="active",
        )
        uow.interviews.add(interview)
        uow.flush()
        section = create_coding_section_for_interview(
            uow.session,
            interview,
            task_count=1,
            status="completed",
        )
        tasks = attach_coding_tasks(uow.session, section, task_ids=["cod-001"])
        task = tasks[0]
        task.submitted_code = "def solve():\n    return 1"
        task.score = 4
        task.feedback = "Works for the sample case."
        task.submit_test_summary = json.dumps(
            {"status": "success", "tests_passed": 2, "tests_total": 2}
        )
        uow.session.add(task)
        overall_feedback = {
            "overall_feedback": "Good coding performance.",
            "strengths_summary": ["problem solving"],
            "topics_to_review": [],
            "score_breakdown": {
                "coding": {
                    "score": 4,
                    "max": 5,
                    "skipped": False,
                    "questions": {"cod-001": {"score": 4, "max": 5}},
                }
            },
        }
        aggregate = uow.interviews.get_aggregate(interview_id)
        assert aggregate is not None
        completed = aggregate.with_session_completed(overall_feedback)
        uow.interviews.save_aggregate(completed)
    return interview_id


@pytest.mark.asyncio
async def test_coding_evaluator_evaluate_section() -> None:
    """Coding section evaluation returns parsed section narrative."""
    provider = FakeProvider(
        replies=[section_evaluation_json(section_feedback="Strong coding section.")]
    )
    result = await CodingEvaluatorService.evaluate_section(
        provider=provider,
        task_submissions=[
            {
                "task_id": "cod-001",
                "round": 0,
                "prompt_text": "Solve it.",
                "submitted_code": "return 1",
                "score": 4,
            }
        ],
        sources_text="Python / junior: basics",
        locale="en",
    )
    assert result.section_feedback == "Strong coding section."


def test_theory_review_service_builds_chat_history(isolated_db) -> None:
    """Theory review exposes answered rounds and fallback section feedback."""
    interview_id = _seed_completed_theory_interview()
    context = TheoryReviewService.build_context(interview_id)
    assert context is not None
    assert len(context.answers) == 1
    assert context.answers[0].feedback == "Clear and concise."
    assert "Clear and concise." in context.section_feedback["section_feedback"]


def test_coding_review_service_groups_task_rounds(isolated_db) -> None:
    """Coding review groups submitted rounds on one page."""
    interview_id = _seed_completed_coding_interview()
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

    context = CodingReviewService.build_context(interview_id)
    assert context is not None
    assert len(context.tasks) == 1
    assert len(context.tasks[0].rounds) == 2
    assert context.tasks[0].total_score == 7


def test_session_results_page_service_builds_section_cards(isolated_db) -> None:
    """Results hub includes enabled section cards with review links."""
    interview_id = _seed_completed_theory_interview("results-hub-1")
    with InterviewUnitOfWork() as uow:
        interview = uow.interviews.get_read_model(interview_id)
    assert interview is not None
    context = SessionResultsPageService.build_context(interview)
    assert context is not None
    assert context.theory_review_url == f"/interview/{interview_id}/theory"
    assert len(context.section_cards) == 1
    assert context.section_cards[0].section == "theory"


def test_completed_interview_page_redirects_to_results(client, isolated_db) -> None:
    """Completed sessions no longer render the active interview page."""
    interview_id = _seed_completed_theory_interview("results-redirect-1")
    response = client.get(f"/interview/{interview_id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/interview/{interview_id}/results"


def test_results_page_renders_for_completed_session(client, isolated_db) -> None:
    """Results hub renders overall feedback and section cards."""
    interview_id = _seed_completed_theory_interview("results-page-1")
    response = client.get(f"/interview/{interview_id}/results")
    assert response.status_code == 200
    assert "Overall Evaluation" in response.text
    assert "View details" in response.text
    assert "Good theory performance." in response.text


def test_theory_review_page_renders_history(client, isolated_db) -> None:
    """Theory review page renders chat history and section feedback."""
    interview_id = _seed_completed_theory_interview("results-theory-page-1")
    response = client.get(f"/interview/{interview_id}/theory")
    assert response.status_code == 200
    assert "Conversation History" in response.text
    assert "A programming language" in response.text
    assert "Clear and concise." in response.text


def test_coding_review_page_renders_task_accordion(client, isolated_db) -> None:
    """Coding review page renders per-task accordion with final submit."""
    interview_id = _seed_completed_coding_interview("results-coding-page-1")
    response = client.get(f"/interview/{interview_id}/coding")
    assert response.status_code == 200
    assert "Coding Tasks" in response.text
    assert "cod-001" in response.text
    assert "Works for the sample case." in response.text
