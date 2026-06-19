# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheoryNavigationService and next_task_payload."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.interview.repositories.uow import InterviewUnitOfWork
from app.theory.domain.entities import TheorySection, TheoryTask
from app.theory.domain.exceptions import (
    TheorySectionNotActiveError,
    TheorySectionNotFoundError,
)
from app.theory.services.navigation import TheoryNavigationService, next_task_payload


def _section_with_tasks(
    interview_id: str = "iv-1",
    *,
    task_time_limit_seconds: int | None = None,
    tasks: list[TheoryTask] | None = None,
    status: str = "active",
) -> TheorySection:
    """Build a theory section with the given tasks."""
    return TheorySection(
        id=1,
        interview_id=interview_id,
        locale="en",
        selection=MagicMock(),
        question_count=2,
        question_ids=("q1", "q2"),
        task_time_limit_seconds=task_time_limit_seconds,
        status=status,
        section_score=None,
        section_feedback=None,
        tasks=tuple(tasks) if tasks else (),
    )


def _task(
    task_id: int,
    question_id: str,
    order: int,
    round_num: int = 0,
    answer_text: str | None = None,
    started_at: datetime | None = None,
) -> TheoryTask:
    """Build a minimal theory task."""
    return TheoryTask(
        id=task_id,
        theory_section_id=1,
        interview_id="iv-1",
        question_id=question_id,
        order=order,
        round=round_num,
        question_text=f"Q{order}?",
        question_code=None,
        answer_text=answer_text,
        score=None,
        feedback=None,
        started_at=started_at,
        created_at=datetime.now(UTC),
        expected_points=(),
    )


def test_next_task_payload_returns_correct_dict() -> None:
    """next_task_payload returns task fields in the expected shape."""
    task = _task(1, "q1", 1)
    payload = next_task_payload(task)

    assert payload == {
        "id": 1,
        "question_id": "q1",
        "order": 1,
        "question_text": "Q1?",
        "question_code": None,
        "round": 0,
    }


def test_advance_to_next_unanswered_returns_next_task_payload() -> None:
    """advance_to_next_unanswered returns the next unanswered task and starts timer."""
    t1 = _task(1, "q1", 1, answer_text="done")
    t2 = _task(2, "q2", 2)
    section = _section_with_tasks(tasks=[t1, t2], task_time_limit_seconds=30)

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryNavigationService(mock_uow)
    payload, timer = service.advance_to_next_unanswered(
        "iv-1",
        question_id="q1",
        round_num=0,
    )

    assert payload is not None
    assert payload["question_id"] == "q2"
    assert payload["order"] == 2
    assert timer is not None
    assert timer <= 30


def test_advance_to_next_unanswered_returns_none_when_complete() -> None:
    """advance_to_next_unanswered returns None when all tasks are answered."""
    t1 = _task(1, "q1", 1, answer_text="done")
    t2 = _task(2, "q2", 2, answer_text="done")
    section = _section_with_tasks(tasks=[t1, t2])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryNavigationService(mock_uow)

    with patch.object(
        service,
        "_notify_phase_complete_if_needed",
    ) as mock_notify:
        payload, timer = service.advance_to_next_unanswered(
            "iv-1",
            question_id="q1",
            round_num=0,
        )

    assert payload is None
    assert timer is None
    mock_notify.assert_called_once_with("iv-1", section)


def test_advance_to_next_unanswered_calls_notify_when_done() -> None:
    """Completing the last task triggers section-complete notification."""
    t1 = _task(1, "q1", 1, answer_text="done")
    t2 = _task(2, "q2", 2, answer_text="done")
    section = _section_with_tasks(tasks=[t1, t2])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryNavigationService(mock_uow)

    with patch.object(
        service,
        "_notify_phase_complete_if_needed",
    ) as mock_notify:
        service.advance_to_next_unanswered(
            "iv-1",
            question_id="q2",
            round_num=0,
        )

    mock_notify.assert_called_once_with("iv-1", section)


def test_advance_raises_when_section_not_found() -> None:
    """TheorySectionNotFoundError is raised when the section does not exist."""
    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = None

    service = TheoryNavigationService(mock_uow)

    with pytest.raises(TheorySectionNotFoundError):
        service.advance_to_next_unanswered(
            "missing",
            question_id="q1",
            round_num=0,
        )


def test_advance_raises_when_section_not_active() -> None:
    """TheorySectionNotActiveError is raised when the section is not active."""
    t1 = _task(1, "q1", 1)
    section = _section_with_tasks(tasks=[t1], status="completed")

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryNavigationService(mock_uow)

    with pytest.raises(TheorySectionNotActiveError):
        service.advance_to_next_unanswered(
            "iv-1",
            question_id="q1",
            round_num=0,
        )


def test_advance_saves_aggregate_with_started_next_task() -> None:
    """The section aggregate is saved with the next task timer started."""
    t1 = _task(1, "q1", 1, answer_text="done")
    t2 = _task(2, "q2", 2)
    section = _section_with_tasks(tasks=[t1, t2], task_time_limit_seconds=30)

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryNavigationService(mock_uow)
    service.advance_to_next_unanswered(
        "iv-1",
        question_id="q1",
        round_num=0,
    )

    saved = mock_uow.theory_sections.save_aggregate.call_args[0][0]
    assert saved is not None
    second_task = next(t for t in saved.tasks if t.id == 2)
    assert second_task.started_at is not None
