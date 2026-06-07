# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test helpers for seeding interview sessions in the database."""

import json

from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import Answer, Interview
from tests.helpers.selection import minimal_selection_spec


def persist_interview_with_answers(
    interview: Interview,
    answers: list[Answer],
) -> str:
    """Persist an interview row and nested answer rows in one transaction.

    Args:
        interview: ORM interview instance to insert.
        answers: Answer rows attached via ``Interview.answers``.

    Returns:
        The interview id.
    """
    interview_id = interview.id
    interview.answers = answers
    with InterviewUnitOfWork(auto_commit=True) as uow:
        uow.interviews.add(interview)
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
            question_count=2,
            question_ids=json.dumps(["q1", "q2"]),
            status="active",
        ),
        [
            Answer(
                interview_id=interview_id,
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
            ),
            Answer(
                interview_id=interview_id,
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            ),
        ],
    )
