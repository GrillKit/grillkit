# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for section review support helpers."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.interview.domain.entities import Interview
from app.interview.domain.serialization import session_to_spec
from app.interview.domain.value_objects import (
    SectionKind,
    SessionSelection,
    TrackSelection,
)
from app.interview.schemas.interview import InterviewRead
from app.interview.services.read_model import load_interview_read
from app.interview.services.section_review_support import (
    CompletedInterviewSnapshot,
    item_id_key_for,
    load_completed_interview,
    resolved_section_feedback,
    review_score_fields,
    section_score_bounds,
    shared_review_fields,
)
from app.interview.services.sections import SectionEvaluationSummary


def _completed_read(
    *,
    status: str = "completed",
    selection_spec: str = "{}",
) -> InterviewRead:
    return InterviewRead(
        id="iv-1",
        status=status,
        locale="en",
        selection_spec=selection_spec,
        question_ids='["q1"]',
        question_count=1,
        question_time_limit_seconds=None,
        answers=[],
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _snapshot() -> CompletedInterviewSnapshot:
    selection = SessionSelection.theory_only(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics",),
            ),
        )
    )
    interview = _completed_read(selection_spec=session_to_spec(selection))
    return CompletedInterviewSnapshot(
        interview=interview,
        session=selection,
    )


class TestLoadCompletedInterview:
    """Tests for load_completed_interview."""

    def test_returns_none_for_incomplete_interview(self) -> None:
        uow = MagicMock()
        active_read = _completed_read(status="active")
        with patch(
            "app.interview.services.section_review_support.load_interview_read",
            return_value=active_read,
        ):
            result = load_completed_interview(uow, "iv-1")
        assert result is None

    def test_returns_none_when_interview_missing(self) -> None:
        uow = MagicMock()
        with patch(
            "app.interview.services.section_review_support.load_interview_read",
            return_value=None,
        ):
            result = load_completed_interview(uow, "iv-1")
        assert result is None

    def test_returns_snapshot_for_completed(self) -> None:
        uow = MagicMock()
        selection = SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        )
        read = _completed_read(
            selection_spec=session_to_spec(selection),
        )
        with patch(
            "app.interview.services.section_review_support.load_interview_read",
            return_value=read,
        ):
            result = load_completed_interview(uow, "iv-1")
        assert result is not None
        assert isinstance(result, CompletedInterviewSnapshot)
        assert result.interview.id == "iv-1"
        assert result.interview.status == "completed"


class TestSectionScoreBounds:
    """Tests for section_score_bounds."""

    def test_skipped_zero_zero_returns_zeros(self) -> None:
        assert section_score_bounds(skipped=True, total_score=0, max_score=0) == (0, 0)

    def test_skipped_with_score_returns_actual(self) -> None:
        assert section_score_bounds(skipped=True, total_score=3, max_score=5) == (3, 5)

    def test_not_skipped_returns_actual(self) -> None:
        assert section_score_bounds(skipped=False, total_score=7, max_score=10) == (
            7,
            10,
        )


class TestSharedReviewFields:
    """Tests for shared_review_fields."""

    def test_builds_correct_fields(self) -> None:
        snapshot = _snapshot()
        fields = shared_review_fields("iv-1", snapshot)
        assert fields["interview_id"] == "iv-1"
        assert fields["results_url"] == "/interview/iv-1/results"
        assert fields["locale_label"] == "English"
        assert "interview_title" in fields
        assert "selection_lines" in fields

    def test_locale_label_for_unknown_locale(self) -> None:
        selection = SessionSelection.theory_only(sources=())
        interview = InterviewRead(
            id="iv-2",
            status="completed",
            locale="zz",
            selection_spec=session_to_spec(selection),
            question_ids="[]",
            question_count=0,
            question_time_limit_seconds=None,
            answers=[],
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            completed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        snapshot = CompletedInterviewSnapshot(
            interview=interview,
            session=selection,
        )
        fields = shared_review_fields("iv-2", snapshot)
        assert fields["locale_label"] == "zz"


class TestResolvedSectionFeedback:
    """Tests for resolved_section_feedback."""

    def test_uses_cached_payload(self) -> None:
        cached = {"section_feedback": "Cached."}
        summary = SectionEvaluationSummary(
            section="theory",
            score=5,
            max_score=5,
            items=(),
        )
        with patch(
            "app.interview.services.section_review_support.resolve_section_feedback",
            return_value=cached,
        ) as mock_resolve:
            result = resolved_section_feedback(
                summary,
                item_id_key="question_id",
                cached_payload=cached,
            )
        mock_resolve.assert_called_once_with(
            cached,
            (),
            item_id_key="question_id",
        )
        assert result == cached

    def test_falls_back_to_summary_items(self) -> None:
        summary = SectionEvaluationSummary(
            section="theory",
            score=5,
            max_score=5,
            items=(
                {
                    "question_id": "q1",
                    "score": 4,
                    "feedback": "Good.",
                },
            ),
        )
        with patch(
            "app.interview.services.section_review_support.resolve_section_feedback",
            return_value={"section_feedback": "Good."},
        ) as mock_resolve:
            result = resolved_section_feedback(
                summary,
                item_id_key="question_id",
                cached_payload=None,
            )
        mock_resolve.assert_called_once_with(
            None,
            summary.items,
            item_id_key="question_id",
        )
        assert result["section_feedback"] == "Good."


class TestReviewScoreFields:
    """Tests for review_score_fields."""

    def test_normalizes_skipped_zero_zero(self) -> None:
        summary = SectionEvaluationSummary(
            section="theory",
            score=0,
            max_score=0,
            items=(),
            skipped=True,
        )
        result = review_score_fields(summary, total_score=0, max_score=0)
        assert result == {"section_score": 0, "section_max_score": 0}

    def test_normalizes_active_scores(self) -> None:
        summary = SectionEvaluationSummary(
            section="theory",
            score=7,
            max_score=10,
            items=(),
            skipped=False,
        )
        result = review_score_fields(summary, total_score=7, max_score=10)
        assert result == {"section_score": 7, "section_max_score": 10}

    def test_uses_aggregate_scores_over_summary(self) -> None:
        summary = SectionEvaluationSummary(
            section="coding",
            score=3,
            max_score=5,
            items=(),
            skipped=False,
        )
        result = review_score_fields(summary, total_score=8, max_score=10)
        assert result == {"section_score": 8, "section_max_score": 10}


class TestItemIdKeyFor:
    """Tests for item_id_key_for."""

    def test_theory_returns_question_id(self) -> None:
        assert item_id_key_for("theory") == "question_id"

    def test_coding_returns_task_id(self) -> None:
        assert item_id_key_for("coding") == "task_id"
