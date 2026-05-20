# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview creation against a temporary question bank."""

import json

import pytest

from app.services.interview_creation import InterviewCreationService
from app.services.interview_query import InterviewQuery
from app.uow import UnitOfWork


def test_create_interview_persists_questions(
    isolated_db, temp_questions_dir, monkeypatch
):
    """create_interview loads YAML, shuffles, and stores answer rows."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = InterviewCreationService.create_interview(
        level="junior",
        category="data-structures",
        language="python",
        locale="en",
        question_count=1,
    )

    assert interview.id
    assert interview.status == "active"
    assert interview.question_count == 1
    assert interview.locale == "en"

    question_ids = json.loads(interview.question_ids)
    assert len(question_ids) == 1
    assert question_ids[0] == "ds-001"

    reloaded = InterviewQuery.get_interview(interview.id)
    assert reloaded is not None
    assert len(reloaded.answers) == 1
    answer = reloaded.answers[0]
    assert answer.question_id == "ds-001"
    assert answer.round == 0
    assert answer.order == 1
    assert answer.answer_text is None
    assert "list" in answer.question_text.lower()


def test_create_interview_unknown_category_raises(isolated_db, temp_questions_dir):
    """Missing category in the bank raises ValueError."""
    del temp_questions_dir
    with pytest.raises(ValueError, match="No questions found"):
        InterviewCreationService.create_interview(
            level="junior",
            category="nonexistent",
            language="python",
            question_count=1,
        )


def test_create_interview_expunged_instance_is_usable(isolated_db, temp_questions_dir):
    """Returned interview is detached but id and fields remain readable."""
    del temp_questions_dir
    interview = InterviewCreationService.create_interview(
        level="junior",
        category="algorithms",
        language="python",
        question_count=1,
    )

    assert interview.id
    assert interview.category == "algorithms"

    with UnitOfWork() as uow:
        stored = uow.interviews.get(interview.id)
    assert stored is not None
    assert stored.id == interview.id
