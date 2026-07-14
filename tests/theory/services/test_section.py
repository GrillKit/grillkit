# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheorySectionService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.sections import SectionEvaluationSummary, SectionPageContext
from app.theory.domain.entities import TheorySection, TheoryTask
from app.theory.services.query import TheoryQueryService
from app.theory.services.section import TheorySectionService


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


def _section(
    *,
    tasks: list[TheoryTask] | None = None,
    status: str = "active",
) -> TheorySection:
    """Build a theory section with the given tasks."""
    return TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        question_count=2,
        question_ids=("q1", "q2"),
        task_time_limit_seconds=None,
        status=status,
        section_score=None,
        section_feedback=None,
        tasks=tuple(tasks) if tasks else (),
    )


def _mock_uow(section: TheorySection | None = None) -> MagicMock:
    """Build a mock UoW that returns the given section."""
    mock = MagicMock(spec=InterviewUnitOfWork)
    mock.theory_sections.get_aggregate.return_value = section
    return mock


def test_is_complete_returns_true_when_all_tasks_answered() -> None:
    """is_complete returns True when every task has answer_text."""
    section = _section(tasks=[_task(1, "q1", 1, "A1"), _task(2, "q2", 2, "A2")])
    service = TheorySectionService(_mock_uow(section))

    assert service.is_complete("iv-1") is True


def test_is_complete_returns_false_when_tasks_remain() -> None:
    """is_complete returns False when at least one task is unanswered."""
    section = _section(tasks=[_task(1, "q1", 1, "A1"), _task(2, "q2", 2)])
    service = TheorySectionService(_mock_uow(section))

    assert service.is_complete("iv-1") is False


def test_is_complete_returns_false_when_no_section() -> None:
    """is_complete returns False when no theory section exists."""
    service = TheorySectionService(_mock_uow(None))

    assert service.is_complete("iv-1") is False


def test_is_user_facing_returns_true_when_unanswered_remain() -> None:
    """is_user_facing returns True when the section exists and is incomplete."""
    section = _section(tasks=[_task(1, "q1", 1, "A1"), _task(2, "q2", 2)])
    service = TheorySectionService(_mock_uow(section))

    assert service.is_user_facing("iv-1") is True


def test_is_user_facing_returns_false_when_complete() -> None:
    """is_user_facing returns False when the section is fully answered."""
    section = _section(tasks=[_task(1, "q1", 1, "A1"), _task(2, "q2", 2, "A2")])
    service = TheorySectionService(_mock_uow(section))

    assert service.is_user_facing("iv-1") is False


def test_is_user_facing_returns_false_when_no_section() -> None:
    """is_user_facing returns False when no theory section exists."""
    service = TheorySectionService(_mock_uow(None))

    assert service.is_user_facing("iv-1") is False


def test_activate_if_pending_always_returns_false() -> None:
    """Theory sections are created active, so activate_if_pending is always False."""
    service = TheorySectionService(_mock_uow(_section()))

    assert service.activate_if_pending("iv-1") is False


def test_get_page_context_returns_correct_context() -> None:
    """get_page_context returns active=True/complete=False for incomplete sections."""
    section = _section(tasks=[_task(1, "q1", 1), _task(2, "q2", 2)])
    service = TheorySectionService(_mock_uow(section))

    ctx = service.get_page_context("iv-1")

    assert isinstance(ctx, SectionPageContext)
    assert ctx.section == "theory"
    assert ctx.active is True
    assert ctx.complete is False


def test_get_page_context_returns_complete_context() -> None:
    """get_page_context returns active=False/complete=True for completed sections."""
    section = _section(tasks=[_task(1, "q1", 1, "A1"), _task(2, "q2", 2, "A2")])
    service = TheorySectionService(_mock_uow(section))

    ctx = service.get_page_context("iv-1")

    assert ctx.complete is True
    assert ctx.active is False


def test_get_page_context_returns_none_when_no_section() -> None:
    """get_page_context returns None when no theory section exists."""
    service = TheorySectionService(_mock_uow(None))

    assert service.get_page_context("iv-1") is None


def test_get_evaluation_summary_delegates_to_query_service() -> None:
    """get_evaluation_summary delegates to the injected TheoryQueryService."""
    summary = SectionEvaluationSummary(
        section="theory",
        score=4,
        max_score=5,
        items=(),
    )
    mock_query = MagicMock(spec=TheoryQueryService)
    mock_query.get_evaluation_summary.return_value = summary
    mock_uow = _mock_uow(_section())

    service = TheorySectionService(mock_uow, query=mock_query)
    result = service.get_evaluation_summary("iv-1")

    assert result == summary
    mock_query.get_evaluation_summary.assert_called_once_with("iv-1")


def test_on_phase_complete_prefetches_feedback() -> None:
    """on_phase_complete delegates to the feedback prefetch helper."""
    mock_feedback = MagicMock()
    mock_feedback.on_phase_complete = MagicMock()

    section = _section(tasks=[_task(1, "q1", 1, "A1")])
    service = TheorySectionService(_mock_uow(section))

    # Replace the private _feedback helper with our mock
    service._feedback = mock_feedback
    service.on_phase_complete("iv-1")

    mock_feedback.on_phase_complete.assert_called_once_with("iv-1")


@pytest.mark.asyncio
async def test_ensure_section_feedback_delegates_to_prefetch() -> None:
    """ensure_section_feedback delegates to the feedback prefetch helper."""
    mock_feedback = MagicMock()
    mock_feedback.ensure_section_feedback = AsyncMock()

    section = _section(tasks=[_task(1, "q1", 1, "A1")])
    service = TheorySectionService(_mock_uow(section))
    service._feedback = mock_feedback

    await service.ensure_section_feedback("iv-1")

    mock_feedback.ensure_section_feedback.assert_awaited_once_with("iv-1")
