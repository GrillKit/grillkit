# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview scoring helpers."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.coding.domain.entities import CodingSection, CodingTask
from app.interview.domain.entities import Interview
from app.interview.domain.value_objects import (
    InterviewSelection,
    SessionSelection,
    TrackSelection,
)
from app.interview.services.scoring import (
    _section_display_score,
    completed_score_fallback,
    resolve_completed_read_score,
    score_from_overall_feedback,
)
from app.theory.domain.entities import TheorySection, TheoryTask


def _shell(
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
    if status == "completed":
        return base.with_session_completed(overall_feedback or {})
    return base


def _theory_section(
    *,
    status: str = "active",
    section_score: int | None = None,
    tasks: tuple[TheoryTask, ...] | None = None,
) -> TheorySection:
    base_tasks = tasks or (
        TheoryTask(
            id=1,
            theory_section_id=1,
            interview_id="iv-1",
            question_id="q1",
            order=1,
            round=0,
            question_text="Q1",
            question_code=None,
            answer_text="answer",
            score=4,
            feedback=None,
            started_at=None,
            created_at=datetime.now(UTC),
        ),
    )
    return TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(sources=()),
        question_count=len(base_tasks),
        question_ids=tuple(t.question_id for t in base_tasks),
        task_time_limit_seconds=None,
        status=status,  # type: ignore[arg-type]
        section_score=section_score,
        section_feedback=None,
        tasks=base_tasks,
    )


def _coding_section(
    *,
    status: str = "active",
    section_score: int | None = None,
    tasks: tuple[CodingTask, ...] | None = None,
) -> CodingSection:
    base_tasks = tasks or (
        CodingTask(
            id=1,
            coding_section_id=1,
            interview_id="iv-1",
            task_id="cod-001",
            order=1,
            round=0,
            prompt_text="Task 1",
            task_spec={},
            submitted_code="def solve(): pass",
            submit_test_summary=None,
            score=3,
            feedback=None,
            started_at=None,
            created_at=datetime.now(UTC),
        ),
    )
    return CodingSection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(sources=()),
        task_count=len(base_tasks),
        task_ids=tuple(t.task_id for t in base_tasks),
        task_time_limit_seconds=None,
        status=status,  # type: ignore[arg-type]
        section_score=section_score,
        section_feedback=None,
        tasks=base_tasks,
    )


class TestScoreFromOverallFeedback:
    """Tests for score_from_overall_feedback."""

    def test_none_feedback_returns_none(self) -> None:
        assert score_from_overall_feedback(None) is None

    def test_missing_breakdown_returns_none(self) -> None:
        assert score_from_overall_feedback({"other": 1}) is None

    def test_empty_breakdown_returns_none(self) -> None:
        assert score_from_overall_feedback({"score_breakdown": {}}) is None

    def test_extracts_total_score_from_breakdown(self) -> None:
        feedback = {"score_breakdown": {"theory": {"score": 4}}}
        with patch(
            "app.interview.services.scoring.SessionEvaluationAggregator.total_score_from_breakdown",
            return_value=9,
        ):
            assert score_from_overall_feedback(feedback) == 9


class TestSectionDisplayScore:
    """Tests for _section_display_score."""

    def test_skipped_section_returns_zero(self) -> None:
        section = _theory_section(status="skipped")
        assert _section_display_score(section) == 0

    def test_uses_section_score_when_set(self) -> None:
        section = _theory_section(section_score=7)
        assert _section_display_score(section) == 7

    def test_falls_back_to_total_score(self) -> None:
        section = _theory_section(section_score=None)
        assert _section_display_score(section) == 4


class TestCompletedScoreFallback:
    """Tests for completed_score_fallback."""

    def test_both_none_returns_none(self) -> None:
        assert completed_score_fallback(_shell(), None, None) is None

    def test_theory_only_returns_theory_score(self) -> None:
        section = _theory_section(section_score=8)
        assert completed_score_fallback(_shell(), section, None) == 8

    def test_coding_only_returns_coding_score(self) -> None:
        section = _coding_section(section_score=6)
        assert completed_score_fallback(_shell(), None, section) == 6

    def test_both_sections_sums_scores(self) -> None:
        theory = _theory_section(section_score=5)
        coding = _coding_section(section_score=7)
        assert completed_score_fallback(_shell(), theory, coding) == 12

    def test_skipped_sections_count_as_zero(self) -> None:
        theory = _theory_section(status="skipped")
        coding = _coding_section(section_score=7)
        assert completed_score_fallback(_shell(), theory, coding) == 7


class TestResolveCompletedReadScore:
    """Tests for resolve_completed_read_score."""

    def test_active_session_returns_none(self) -> None:
        shell = _shell(status="active")
        assert resolve_completed_read_score(shell, _theory_section(), None) is None

    def test_uses_overall_feedback_score_when_available(self) -> None:
        shell = _shell(
            status="completed",
            overall_feedback={
                "score_breakdown": {
                    "theory": {"score": 8, "max": 10},
                }
            },
        )
        with patch(
            "app.interview.services.scoring.SessionEvaluationAggregator.total_score_from_breakdown",
            return_value=8,
        ):
            assert resolve_completed_read_score(shell, _theory_section(), None) == 8

    def test_falls_back_to_section_totals(self) -> None:
        shell = _shell(
            status="completed",
            overall_feedback={"not_breakdown": 1},
        )
        theory = _theory_section(section_score=None)
        with patch(
            "app.interview.services.scoring.SessionEvaluationAggregator.total_score_from_breakdown",
            return_value=None,
        ):
            assert resolve_completed_read_score(shell, theory, None) == 4

    def test_feedback_score_takes_precedence_over_fallback(self) -> None:
        shell = _shell(
            status="completed",
            overall_feedback={
                "score_breakdown": {
                    "theory": {"score": 10, "max": 10},
                }
            },
        )
        theory = _theory_section(section_score=3)
        with patch(
            "app.interview.services.scoring.SessionEvaluationAggregator.total_score_from_breakdown",
            return_value=10,
        ):
            assert resolve_completed_read_score(shell, theory, None) == 10

    def test_null_breakdown_uses_fallback(self) -> None:
        shell = _shell(
            status="completed",
            overall_feedback=None,
        )
        theory = _theory_section(section_score=6)
        assert resolve_completed_read_score(shell, theory, None) == 6
