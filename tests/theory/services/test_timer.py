# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheoryTimerService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.events import AnswerFeedbackEvent
from app.theory.domain.entities import TheorySection, TheoryTask
from app.theory.domain.exceptions import TheorySectionNotFoundError
from app.theory.services.navigation import TheoryNavigationService
from app.theory.services.timer import TheoryTimerService


def _task(
    task_id: int,
    question_id: str,
    order: int,
    answer_text: str | None = None,
) -> TheoryTask:
    """Build a minimal theory task."""
    return TheoryTask(
        id=task_id,
        theory_section_id=1,
        interview_id="iv-1",
        question_id=question_id,
        order=order,
        round=0,
        question_text=f"Q{order}?",
        question_code=None,
        answer_text=answer_text,
        score=None,
        feedback=None,
        started_at=None,
        created_at=datetime.now(UTC),
        expected_points=(),
    )


def _section(tasks: list[TheoryTask]) -> TheorySection:
    """Build a theory section with the given tasks."""
    return TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=MagicMock(),
        question_count=len(tasks),
        question_ids=tuple(t.question_id for t in tasks),
        task_time_limit_seconds=None,
        status="active",
        section_score=None,
        section_feedback=None,
        tasks=tuple(tasks),
    )


def test_persist_timed_out_round_saves_timeout_with_zero_score() -> None:
    """persist_timed_out_round marks the task with timeout text and score 0."""
    t1 = _task(1, "q1", 1)
    section = _section([t1])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    mock_nav = MagicMock(spec=TheoryNavigationService)
    mock_nav.advance_to_next_unanswered.return_value = (None, None)

    service = TheoryTimerService(mock_uow, navigation=mock_nav)

    with patch(
        "app.theory.services.timer.timeout_feedback_for_locale",
        return_value="Time is up",
    ):
        service.persist_timed_out_round(
            interview_id="iv-1",
            question_id="q1",
            round_num=0,
            order=1,
            locale="en",
        )

    saved = mock_uow.theory_sections.save_aggregate.call_args[0][0]
    assert saved is not None
    task = next(t for t in saved.tasks if t.question_id == "q1" and t.round == 0)
    assert task.answer_text == TheoryTask.TIME_EXPIRED_ANSWER_TEXT
    assert task.score == 0
    assert task.feedback == "Time is up"


def test_persist_timed_out_round_returns_feedback_event() -> None:
    """persist_timed_out_round returns an AnswerFeedbackEvent with timed_out=True."""
    t1 = _task(1, "q1", 1)
    section = _section([t1])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    mock_nav = MagicMock(spec=TheoryNavigationService)
    mock_nav.advance_to_next_unanswered.return_value = (
        {"id": 2, "question_id": "q2", "order": 2},
        45,
    )

    service = TheoryTimerService(mock_uow, navigation=mock_nav)

    with patch(
        "app.theory.services.timer.timeout_feedback_for_locale",
        return_value="Time is up",
    ):
        result = service.persist_timed_out_round(
            interview_id="iv-1",
            question_id="q1",
            round_num=0,
            order=1,
            locale="en",
        )

    assert isinstance(result, AnswerFeedbackEvent)
    assert result.timed_out is True
    assert result.question_id == "q1"
    assert result.order == 1
    assert result.round == 0
    assert result.feedback == "Time is up"
    assert result.follow_up_needed is False
    assert result.follow_up_text is None


def test_persist_timed_out_round_advances_to_next_question() -> None:
    """persist_timed_out_round calls navigation to advance after saving timeout."""
    t1 = _task(1, "q1", 1)
    section = _section([t1])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    mock_nav = MagicMock(spec=TheoryNavigationService)
    mock_nav.advance_to_next_unanswered.return_value = (None, None)

    service = TheoryTimerService(mock_uow, navigation=mock_nav)

    with patch(
        "app.theory.services.timer.timeout_feedback_for_locale",
        return_value="Time is up",
    ):
        service.persist_timed_out_round(
            interview_id="iv-1",
            question_id="q1",
            round_num=0,
            order=1,
            locale="en",
        )

    mock_nav.advance_to_next_unanswered.assert_called_once_with(
        "iv-1",
        question_id="q1",
        round_num=0,
    )


def test_persist_timed_out_round_uses_locale_specific_feedback() -> None:
    """Locale is passed to timeout_feedback_for_locale for localized text."""
    t1 = _task(1, "q1", 1)
    section = _section([t1])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    mock_nav = MagicMock(spec=TheoryNavigationService)
    mock_nav.advance_to_next_unanswered.return_value = (None, None)

    service = TheoryTimerService(mock_uow, navigation=mock_nav)

    with patch(
        "app.theory.services.timer.timeout_feedback_for_locale",
        return_value="Время вышло",
    ) as mock_feedback:
        result = service.persist_timed_out_round(
            interview_id="iv-1",
            question_id="q1",
            round_num=0,
            order=1,
            locale="ru",
        )

    mock_feedback.assert_called_once_with("ru")
    assert result.feedback == "Время вышло"


def test_persist_timed_out_round_raises_when_section_not_found() -> None:
    """TheorySectionNotFoundError is raised when the section does not exist."""
    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = None

    service = TheoryTimerService(mock_uow)

    with pytest.raises(TheorySectionNotFoundError):
        service.persist_timed_out_round(
            interview_id="missing",
            question_id="q1",
            round_num=0,
            order=1,
            locale="en",
        )
