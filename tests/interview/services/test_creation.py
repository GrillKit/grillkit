# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview creation against a temporary question bank."""

import json

import pytest

from app.coding.repositories.uow import CodingUnitOfWork
from app.interview.domain.value_objects import (
    InterviewSelection,
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.creation import SessionCreationService
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.selection import get_interview_selection


def _session_from_selection(
    selection: InterviewSelection,
    *,
    question_count: int = 5,
    task_time_limit_seconds: int | None = None,
) -> SessionSelection:
    """Wrap a legacy theory selection in a v2 session selection."""
    return SessionSelection.theory_only(
        sources=selection.sources,
        question_count=question_count,
        task_time_limit_seconds=task_time_limit_seconds,
    )


def _single_selection(
    *,
    track: str = "python",
    level: str = "junior",
    categories: tuple[str, ...] | None = None,
) -> InterviewSelection:
    """Build a single-track selection for tests."""
    return InterviewSelection(
        sources=(
            TrackSelection(
                track=track,
                level=level,
                categories=categories or ("data-structures",),
            ),
        )
    )


def test_create_interview_persists_questions(
    isolated_db, temp_questions_dir, monkeypatch
):
    """create_interview loads YAML, shuffles, and stores answer rows."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = SessionCreationService.create_session(
        _session_from_selection(_single_selection(), question_count=1),
        locale="en",
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

    interview = SessionCreationService.create_session(
        _session_from_selection(
            _single_selection(),
            question_count=1,
            task_time_limit_seconds=180,
        ),
        locale="en",
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
        SessionCreationService.create_session(
            _session_from_selection(
                _single_selection(categories=("nonexistent",)),
                question_count=1,
            ),
        )


def test_create_interview_expunged_instance_is_usable(isolated_db, temp_questions_dir):
    """Returned interview is detached but id and fields remain readable."""
    del temp_questions_dir
    interview = SessionCreationService.create_session(
        _session_from_selection(
            _single_selection(categories=("algorithms",)),
            question_count=1,
        ),
    )

    assert interview.id
    assert "algorithms" in interview.selection_spec
    question_ids = json.loads(interview.question_ids)
    assert question_ids == ["algo-002"]

    with InterviewUnitOfWork() as uow:
        stored = uow.interviews.get(interview.id)
    assert stored is not None
    assert stored.id == interview.id


def test_create_multi_topic_interview(isolated_db, temp_questions_dir, monkeypatch):
    """Multi-topic selection is stored only in selection_spec."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("data-structures", "algorithms"),
            ),
        )
    )
    interview = SessionCreationService.create_session(
        _session_from_selection(selection, question_count=2),
    )

    assert interview.question_count == 2
    assert interview.selection_spec
    assert "data-structures" in interview.selection_spec
    assert "algorithms" in interview.selection_spec

    reloaded = InterviewQuery.get_interview(interview.id)
    assert reloaded is not None
    parsed = get_interview_selection(reloaded)
    assert len(parsed.sources[0].categories) == 2


def test_create_coding_only_session(isolated_db, monkeypatch) -> None:
    """Coding-only sessions persist a coding section with planned tasks."""
    monkeypatch.setattr("random.shuffle", lambda items: None)

    session = SessionSelection(
        session_mode="coding_only",
        theory=SectionBranchSpec(
            enabled=False,
            question_count=0,
            task_time_limit_seconds=None,
            sources=(),
        ),
        coding=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=600,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
        ),
    )
    interview = SessionCreationService.create_session(session, locale="en")

    assert interview.id
    assert interview.status == "active"
    assert "coding_only" in interview.selection_spec

    with CodingUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    assert section.status == "active"
    assert section.task_count == 1
    assert len(section.tasks) == 1
    assert section.tasks[0].task_id.startswith("bas-")
    assert section.task_time_limit_seconds == 600


def test_create_theory_then_coding_session_pending_coding(
    isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Theory-first mixed sessions keep coding pending until the theory phase ends."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    session = SessionSelection(
        session_mode="theory_then_coding",
        theory=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=None,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("data-structures",),
                ),
            ),
        ),
        coding=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=None,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
        ),
    )
    interview = SessionCreationService.create_session(session, locale="en")

    with CodingUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    assert section.status == "pending"
