# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for multi-source interview selection planning."""

import pytest

from app.interview.domain.selection import (
    InterviewSelection,
    LanguageQuestionPools,
    LanguageSelection,
    parse_selection_spec,
    plan_questions,
    selection_to_spec,
    validate_question_count,
)
from app.questions import Question


def _question(qid: str, lang_marker: str = "") -> Question:
    """Build a minimal Question for planning tests."""
    return Question(
        id=qid,
        type="knowledge",
        difficulty=1,
        tags=[],
        text=f"Question {qid} {lang_marker}",
        code=None,
        follow_ups=[],
        expected_points=[],
    )


class TestValidateQuestionCount:
    """Tests for question count vs topic count validation."""

    def test_rejects_count_below_topic_count(self):
        """question_count must be at least the number of selected topics."""
        selection = InterviewSelection(
            sources=[
                LanguageSelection(
                    language="python",
                    level="junior",
                    categories=["basics", "oop"],
                )
            ]
        )
        with pytest.raises(ValueError, match="at least 2"):
            validate_question_count(selection, 1)


class TestPlanQuestions:
    """Tests for plan_questions distribution and ordering."""

    def test_one_question_per_topic_minimum(self):
        """Plan includes at least one question per selected topic."""
        selection = InterviewSelection(
            sources=[
                LanguageSelection(
                    language="python",
                    level="junior",
                    categories=["basics", "oop"],
                )
            ]
        )
        pools = [
            LanguageQuestionPools(
                source=selection.sources[0],
                full_pool=[_question("basics-1"), _question("oop-1")],
                category_pools={
                    "basics": [_question("basics-1")],
                    "oop": [_question("oop-1")],
                },
            )
        ]

        plan = plan_questions(selection, 2, pools)
        assert len(plan) == 2
        ids = {q.id for q in plan}
        assert ids == {"basics-1", "oop-1"}

    def test_orders_by_language_blocks(self, monkeypatch):
        """Questions are grouped by language in source order."""
        selection = InterviewSelection(
            sources=[
                LanguageSelection(
                    language="python",
                    level="junior",
                    categories=["basics"],
                ),
                LanguageSelection(
                    language="database",
                    level="junior",
                    categories=["sql"],
                ),
            ]
        )
        py_pool = [_question("py-1", "py"), _question("py-2", "py")]
        db_pool = [_question("db-1", "db"), _question("db-2", "db")]
        pools = [
            LanguageQuestionPools(
                source=selection.sources[0],
                full_pool=py_pool,
                category_pools={"basics": py_pool},
            ),
            LanguageQuestionPools(
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

    def test_round_trip(self):
        """selection_to_spec and parse_selection_spec preserve data."""
        selection = InterviewSelection(
            sources=[
                LanguageSelection(
                    language="python",
                    level="junior",
                    categories=["basics"],
                )
            ]
        )
        raw = selection_to_spec(selection)
        parsed = parse_selection_spec(raw)
        assert parsed.sources[0].language == "python"
        assert parsed.sources[0].categories == ["basics"]
