# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for multi-source interview selection planning."""

import pytest

from app.interview.domain.serialization import (
    parse_selection_spec,
    parse_session_spec,
    session_to_spec,
)
from app.interview.domain.value_objects import (
    InterviewSelection,
    PlannedQuestion,
    SessionSelection,
    TrackQuestionPools,
    TrackSelection,
)
from app.interview.services.rules.selection import (
    plan_questions,
    validate_question_count,
)


def _question(qid: str, lang_marker: str = "") -> PlannedQuestion:
    """Build a minimal planned question for planning tests."""
    return PlannedQuestion(
        id=qid,
        text=f"Question {qid} {lang_marker}",
        code=None,
    )


class TestValidateQuestionCount:
    """Tests for question count vs topic count validation."""

    def test_rejects_count_below_topic_count(self):
        """question_count must be at least the number of selected topics."""
        selection = InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics", "oop"),
                ),
            )
        )
        with pytest.raises(ValueError, match="at least 2"):
            validate_question_count(selection, 1)


class TestPlanQuestions:
    """Tests for plan_questions distribution and ordering."""

    def test_one_question_per_topic_minimum(self):
        """Plan includes at least one question per selected topic."""
        selection = InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics", "oop"),
                ),
            )
        )
        pools = [
            TrackQuestionPools(
                source=selection.sources[0],
                full_pool=(_question("basics-1"), _question("oop-1")),
                category_pools={
                    "basics": (_question("basics-1"),),
                    "oop": (_question("oop-1"),),
                },
            )
        ]

        plan = plan_questions(selection, 2, pools)
        assert len(plan) == 2
        ids = {q.id for q in plan}
        assert ids == {"basics-1", "oop-1"}

    def test_orders_by_track_blocks(self, monkeypatch):
        """Questions are grouped by track in source order."""
        selection = InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
                TrackSelection(
                    track="database",
                    level="junior",
                    categories=("sql",),
                ),
            )
        )
        py_pool = (_question("py-1", "py"), _question("py-2", "py"))
        db_pool = (_question("db-1", "db"), _question("db-2", "db"))
        pools = [
            TrackQuestionPools(
                source=selection.sources[0],
                full_pool=py_pool,
                category_pools={"basics": py_pool},
            ),
            TrackQuestionPools(
                source=selection.sources[1],
                full_pool=db_pool,
                category_pools={"sql": db_pool},
            ),
        ]
        monkeypatch.setattr("random.shuffle", lambda items: None)

        plan = plan_questions(selection, 4, pools)
        assert len(plan) == 4
        py_indices = [i for i, q in enumerate(plan) if q.id.startswith("py")]
        db_indices = [i for i, q in enumerate(plan) if q.id.startswith("db")]
        assert py_indices
        assert db_indices
        assert max(py_indices) < min(db_indices)


class TestSelectionSpec:
    """Tests for selection_spec JSON round-trip."""

    def test_v2_session_round_trip(self):
        """session_to_spec and parse_session_spec preserve v2 session data."""
        session = SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
            question_count=5,
            task_time_limit_seconds=120,
        )
        raw = session_to_spec(session)
        parsed = parse_session_spec(raw)
        assert parsed.session_mode == "theory_only"
        assert parsed.theory.question_count == 5
        assert parsed.theory.task_time_limit_seconds == 120
        assert parsed.theory_selection.sources[0].track == "python"
        assert '"version":2' in raw
        assert '"session_mode":"theory_only"' in raw

    def test_v1_theory_sources_compat(self):
        """parse_selection_spec extracts theory sources from legacy v1 JSON."""
        selection = InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        )
        raw = (
            '{"sources":[{"track":"python","level":"junior","categories":["basics"]}]}'
        )
        parsed = parse_selection_spec(raw)
        assert parsed.sources[0].track == selection.sources[0].track
        assert parsed.sources[0].categories == selection.sources[0].categories
