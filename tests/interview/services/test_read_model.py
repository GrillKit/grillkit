# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview read model assembly and loading."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.interview.domain.entities import Interview
from app.interview.domain.value_objects import (
    InterviewSelection,
    SessionSelection,
    TrackSelection,
)
from app.interview.schemas.interview import InterviewRead
from app.interview.services.read_model import (
    assemble_interview_read,
    load_interview_read,
    load_recent_interview_reads,
)
from app.theory.domain.entities import TheorySection


def _shell(
    *,
    status: str = "active",
    overall_feedback: dict | None = None,
) -> Interview:
    base = Interview.start_shell(
        "iv-1",
        selection=SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        locale="en",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    if overall_feedback or status == "completed":
        return base.with_session_completed(overall_feedback or {})
    return base


def _theory_section(
    *,
    status: str = "active",
    section_score: int | None = None,
    tasks: tuple | None = None,
) -> TheorySection:
    _ = status, section_score, tasks
    # Rebuild because start validates non-empty planned_questions
    return None  # type: ignore[return-value]


def test_assemble_interview_read_builds_correct_read_model() -> None:
    """assemble_interview_read composes a read model from shell and theory."""
    shell = _shell()
    theory = TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(sources=()),
        question_count=0,
        question_ids=(),
        task_time_limit_seconds=None,
        status="active",
        section_score=None,
        section_feedback=None,
        tasks=(),
    )
    result = assemble_interview_read(shell, theory)
    assert isinstance(result, InterviewRead)
    assert result.id == "iv-1"
    assert result.status == "active"
    assert result.locale == "en"


def test_assemble_interview_read_sets_score_when_completed() -> None:
    """Completed shells get a resolved display score."""
    shell = _shell(
        status="completed",
        overall_feedback={
            "score_breakdown": {
                "theory": {"score": 8, "max": 10},
            }
        },
    )
    theory = TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(sources=()),
        question_count=0,
        question_ids=(),
        task_time_limit_seconds=None,
        status="completed",
        section_score=None,
        section_feedback=None,
        tasks=(),
    )
    with patch(
        "app.interview.services.read_model.resolve_completed_read_score",
        return_value=8,
    ):
        result = assemble_interview_read(shell, theory)
    assert result.score == 8


def test_assemble_interview_read_without_theory() -> None:
    """assemble_interview_read works when theory section is None."""
    shell = _shell()
    result = assemble_interview_read(shell, None)
    assert isinstance(result, InterviewRead)
    assert result.question_count == 0
    assert result.answers == []


def test_load_interview_read_returns_none_when_missing() -> None:
    """load_interview_read returns None for a missing interview."""
    uow = MagicMock()
    uow.interviews.get_aggregate.return_value = None
    assert load_interview_read(uow, "missing") is None
    uow.interviews.get_aggregate.assert_called_once_with("missing")


def test_load_interview_read_returns_assembled_model() -> None:
    """load_interview_read loads aggregates and assembles the read model."""
    shell = _shell()
    theory = TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(sources=()),
        question_count=0,
        question_ids=(),
        task_time_limit_seconds=None,
        status="active",
        section_score=None,
        section_feedback=None,
        tasks=(),
    )
    uow = MagicMock()
    uow.interviews.get_aggregate.return_value = shell
    uow.theory_sections.get_aggregate.return_value = theory
    uow.coding_sections.get_aggregate.return_value = None

    result = load_interview_read(uow, "iv-1")
    assert isinstance(result, InterviewRead)
    assert result.id == "iv-1"
    uow.interviews.get_aggregate.assert_called_once_with("iv-1")
    uow.theory_sections.get_aggregate.assert_called_once_with("iv-1")
    uow.coding_sections.get_aggregate.assert_called_once_with("iv-1")


def test_load_recent_interview_reads_empty_list() -> None:
    """load_recent_interview_reads returns an empty list when there are no shells."""
    uow = MagicMock()
    uow.interviews.list_recent_aggregates.return_value = []
    assert load_recent_interview_reads(uow, limit=20) == []
    uow.interviews.list_recent_aggregates.assert_called_once_with(limit=20)


def test_load_recent_interview_reads_returns_list() -> None:
    """load_recent_interview_reads loads and assembles multiple reads."""
    shell1 = Interview.start_shell(
        "iv-1",
        selection=SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        locale="en",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    shell2 = Interview.start_shell(
        "iv-2",
        selection=SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="go",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        locale="en",
        started_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    uow = MagicMock()
    uow.interviews.list_recent_aggregates.return_value = [shell1, shell2]
    uow.theory_sections.get_aggregates_by_interview_ids.return_value = {}
    uow.coding_sections.get_aggregates_by_interview_ids.return_value = {}

    results = load_recent_interview_reads(uow, limit=10)
    assert len(results) == 2
    assert results[0].id == "iv-1"
    assert results[1].id == "iv-2"
    uow.interviews.list_recent_aggregates.assert_called_once_with(limit=10)


def test_load_recent_interview_reads_with_sections() -> None:
    """Recent reads include theory and coding sections when present."""
    shell = Interview.start_shell(
        "iv-1",
        selection=SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        locale="en",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    theory = TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(sources=()),
        question_count=0,
        question_ids=(),
        task_time_limit_seconds=None,
        status="active",
        section_score=None,
        section_feedback=None,
        tasks=(),
    )
    uow = MagicMock()
    uow.interviews.list_recent_aggregates.return_value = [shell]
    uow.theory_sections.get_aggregates_by_interview_ids.return_value = {
        "iv-1": theory
    }
    uow.coding_sections.get_aggregates_by_interview_ids.return_value = {}

    results = load_recent_interview_reads(uow, limit=10)
    assert len(results) == 1
    assert results[0].id == "iv-1"
