# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding completed interview sessions."""

import json

from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import Answer, Interview
from tests.helpers.coding_seed import (
    attach_coding_tasks,
    create_coding_section_for_interview,
)
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


def seed_completed_theory_interview(interview_id: str = "results-theory-1") -> str:
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


def seed_completed_coding_interview(interview_id: str = "results-coding-1") -> str:
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
