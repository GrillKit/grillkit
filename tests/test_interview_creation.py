# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview creation against a temporary question bank."""

import json

import pytest

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.creation import InterviewCreationService
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.selection import (
    InterviewSelection,
    TrackSelection,
    get_interview_selection,
)


def _single_selection(
    *,
    track: str = "python",
    level: str = "junior",
    categories: list[str] | None = None,
) -> InterviewSelection:
    """Build a single-track selection for tests."""
    return InterviewSelection(
        sources=[
            TrackSelection(
                track=track,
                level=level,
                categories=categories or ["data-structures"],
            )
        ]
    )


def test_create_interview_persists_questions(
    isolated_db, temp_questions_dir, monkeypatch
):
    """create_interview loads YAML, shuffles, and stores answer rows."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = InterviewCreationService.create_interview(
        selection=_single_selection(),
        locale="en",
        question_count=1,
    )

    assert interview.id
    assert interview.status == "active"
    assert interview.question_count == 1
    assert interview.locale == "en"
    assert interview.selection_spec

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
    assert interview.question_time_limit_seconds is None
    assert answer.started_at is None


def test_create_interview_with_timer_starts_first_round(
    isolated_db, temp_questions_dir, monkeypatch
):
    """Timer-enabled sessions store the limit and start the first round clock."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = InterviewCreationService.create_interview(
        selection=_single_selection(),
        locale="en",
        question_count=1,
        question_time_limit_seconds=180,
    )

    assert interview.question_time_limit_seconds == 180

    reloaded = InterviewQuery.get_interview(interview.id)
    assert reloaded is not None
    assert len(reloaded.answers) == 1
    assert reloaded.answers[0].started_at is not None


def test_create_interview_unknown_category_raises(isolated_db, temp_questions_dir):
    """Missing category in the bank raises ValueError."""
    del temp_questions_dir
    with pytest.raises(ValueError, match="Unknown topic"):
        InterviewCreationService.create_interview(
            selection=_single_selection(categories=["nonexistent"]),
            question_count=1,
        )


def test_create_interview_expunged_instance_is_usable(isolated_db, temp_questions_dir):
    """Returned interview is detached but id and fields remain readable."""
    del temp_questions_dir
    interview = InterviewCreationService.create_interview(
        selection=_single_selection(categories=["algorithms"]),
        question_count=1,
    )

    assert interview.id
    assert "algorithms" in interview.selection_spec

    with InterviewUnitOfWork() as uow:
        stored = uow.interviews.get(interview.id)
    assert stored is not None
    assert stored.id == interview.id


def test_create_multi_topic_interview(isolated_db, temp_questions_dir, monkeypatch):
    """Multi-topic selection is stored only in selection_spec."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    selection = InterviewSelection(
        sources=[
            TrackSelection(
                track="python",
                level="junior",
                categories=["data-structures", "algorithms"],
            )
        ]
    )
    interview = InterviewCreationService.create_interview(
        selection=selection,
        question_count=2,
    )

    assert interview.question_count == 2
    assert interview.selection_spec
    assert "data-structures" in interview.selection_spec
    assert "algorithms" in interview.selection_spec

    reloaded = InterviewQuery.get_interview(interview.id)
    assert reloaded is not None
    parsed = get_interview_selection(reloaded)
    assert len(parsed.sources[0].categories) == 2
