# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding interview sessions in the database."""

from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import Answer, Interview
from tests.helpers.selection import minimal_selection_spec
from tests.helpers.theory_seed import attach_theory_section_to_answers


def persist_interview_with_answers(
    interview: Interview,
    answers: list[Answer],
    *,
    question_count: int | None = None,
    task_time_limit_seconds: int | None = None,
) -> str:
    """Persist an interview row and nested answer rows in one transaction.

    Args:
        interview: ORM interview instance to insert.
        answers: Theory task rows to link through a theory section.
        question_count: Section question count; defaults to answer list length.
        task_time_limit_seconds: Optional per-task timer in seconds.

    Returns:
        The interview id.
    """
    interview_id = interview.id
    with InterviewUnitOfWork(auto_commit=True) as uow:
        uow.interviews.add(interview)
        uow.flush()
        attach_theory_section_to_answers(
            uow.session,
            interview,
            answers,
            question_count=question_count,
            task_time_limit_seconds=task_time_limit_seconds,
        )
    return interview_id


def seed_two_question_interview(interview_id: str = "ap-test-1") -> str:
    """Persist an active interview with two unanswered questions.

    Args:
        interview_id: Interview primary key.

    Returns:
        The interview id.
    """
    return persist_interview_with_answers(
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
                question_text="Question one?",
            ),
            Answer(
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            ),
        ],
        question_count=2,
        task_time_limit_seconds=None,
    )
