# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheorySectionCreationService."""

from unittest.mock import patch

import pytest

from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.theory.domain.value_objects import PlannedTheoryQuestion
from app.theory.services.creation import TheorySectionCreationService


_SELECTION = InterviewSelection(
    sources=(
        TrackSelection(
            track="python",
            level="junior",
            categories=("data-structures",),
        ),
    )
)


_PLANNED = (
    PlannedTheoryQuestion(id="q1", text="Q1", code=None, expected_points=()),
    PlannedTheoryQuestion(id="q2", text="Q2", code=None, expected_points=()),
)


def test_create_builds_section_with_planned_questions() -> None:
    """create persists a section with tasks matching the question plan."""
    with patch(
        "app.theory.services.creation.build_theory_question_plan",
        return_value=_PLANNED,
    ):
        mock_uow = InterviewUnitOfWork(auto_commit=False)
        mock_uow.theory_sections.create_aggregate = lambda s: s
        service = TheorySectionCreationService(mock_uow)

        section = service.create(
            interview_id="iv-1",
            selection=_SELECTION,
            locale="en",
            question_count=2,
            task_time_limit_seconds=None,
        )

    assert section.interview_id == "iv-1"
    assert section.locale == "en"
    assert section.question_count == 2
    assert len(section.tasks) == 2
    assert section.tasks[0].question_id == "q1"
    assert section.tasks[1].question_id == "q2"
    assert section.tasks[0].order == 1
    assert section.tasks[1].order == 2


def test_create_validates_question_count() -> None:
    """create raises ValueError when question_count is below the topic count."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("data-structures", "algorithms"),
            ),
        )
    )
    with patch(
        "app.theory.services.creation.build_theory_question_plan",
        return_value=(),
    ):
        mock_uow = InterviewUnitOfWork(auto_commit=False)
        service = TheorySectionCreationService(mock_uow)

        with pytest.raises(ValueError, match="at least 2"):
            service.create(
                interview_id="iv-1",
                selection=selection,
                locale="en",
                question_count=1,
                task_time_limit_seconds=None,
            )


def test_create_starts_first_task_timer_when_enabled() -> None:
    """create starts the first task timer when start_first_task_timer is True."""
    with patch(
        "app.theory.services.creation.build_theory_question_plan",
        return_value=_PLANNED,
    ):
        mock_uow = InterviewUnitOfWork(auto_commit=False)
        mock_uow.theory_sections.create_aggregate = lambda s: s
        service = TheorySectionCreationService(mock_uow)

        section = service.create(
            interview_id="iv-1",
            selection=_SELECTION,
            locale="en",
            question_count=2,
            task_time_limit_seconds=60,
            start_first_task_timer=True,
        )

    assert section.task_time_limit_seconds == 60
    assert section.tasks[0].started_at is not None
    assert section.tasks[1].started_at is None


def test_create_does_not_start_timer_when_disabled() -> None:
    """create leaves started_at None on all tasks when start_first_task_timer is False."""
    with patch(
        "app.theory.services.creation.build_theory_question_plan",
        return_value=_PLANNED,
    ):
        mock_uow = InterviewUnitOfWork(auto_commit=False)
        mock_uow.theory_sections.create_aggregate = lambda s: s
        service = TheorySectionCreationService(mock_uow)

        section = service.create(
            interview_id="iv-1",
            selection=_SELECTION,
            locale="en",
            question_count=2,
            task_time_limit_seconds=60,
            start_first_task_timer=False,
        )

    assert section.tasks[0].started_at is None
    assert section.tasks[1].started_at is None


def test_create_passes_excluded_ids_to_planner() -> None:
    """create forwards excluded_ids to build_theory_question_plan."""
    with patch(
        "app.theory.services.creation.build_theory_question_plan",
        return_value=_PLANNED,
    ) as mock_plan:
        mock_uow = InterviewUnitOfWork(auto_commit=False)
        mock_uow.theory_sections.create_aggregate = lambda s: s
        service = TheorySectionCreationService(mock_uow)

        service.create(
            interview_id="iv-1",
            selection=_SELECTION,
            locale="en",
            question_count=2,
            task_time_limit_seconds=None,
            excluded_ids=frozenset({"q3"}),
        )

    mock_plan.assert_called_once_with(
        _SELECTION,
        2,
        locale="en",
        excluded_ids=frozenset({"q3"}),
    )
