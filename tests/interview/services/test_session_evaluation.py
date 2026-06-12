# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for session evaluation aggregation and completion."""

from unittest.mock import AsyncMock, patch

import pytest

from app.interview.services.evaluation_aggregator import (
    SessionEvaluationAggregator,
    attach_session_score_breakdown,
)
from app.interview.services.sections import SectionEvaluationSummary
from app.interview.services.session_evaluator import SessionEvaluatorService
from tests.fakes import FakeProvider


def test_aggregator_builds_nested_section_breakdown() -> None:
    """Merged evaluation exposes per-section score breakdown."""
    theory = SectionEvaluationSummary(
        section="theory",
        score=4,
        max_score=5,
        items=(
            {
                "question_id": "q1",
                "question_text": "Question?",
                "answer_text": "Answer",
                "score": 4,
                "round": 0,
            },
        ),
    )
    merged = SessionEvaluationAggregator.merge(theory, None)
    breakdown = merged.to_score_breakdown()
    assert breakdown["theory"]["score"] == 4
    assert breakdown["theory"]["questions"]["q1"]["score"] == 4
    assert SessionEvaluationAggregator.total_score_from_breakdown(breakdown) == 4


def test_aggregator_merges_theory_and_coding_breakdown() -> None:
    """Merged evaluation exposes separate theory and coding section scores."""
    theory = SectionEvaluationSummary(
        section="theory",
        score=4,
        max_score=5,
        items=(
            {
                "question_id": "q1",
                "question_text": "Question?",
                "answer_text": "Answer",
                "score": 4,
                "round": 0,
            },
        ),
    )
    coding = SectionEvaluationSummary(
        section="coding",
        score=3,
        max_score=5,
        items=(
            {
                "task_id": "cod-001",
                "prompt_text": "Write a function",
                "submitted_code": "def solve():\n    return 1",
                "score": 3,
                "round": 0,
            },
        ),
    )
    merged = SessionEvaluationAggregator.merge(theory, coding)
    breakdown = merged.to_score_breakdown()
    assert breakdown["theory"]["score"] == 4
    assert breakdown["coding"]["score"] == 3
    assert breakdown["coding"]["questions"]["cod-001"]["score"] == 3
    assert SessionEvaluationAggregator.total_score_from_breakdown(breakdown) == 7


@pytest.mark.asyncio
async def test_evaluate_session_synthesizes_when_llm_returns_empty_json() -> None:
    """Session completion falls back to per-answer feedback when LLM output is empty."""
    theory = SectionEvaluationSummary(
        section="theory",
        score=4,
        max_score=5,
        items=(
            {
                "question_id": "q1",
                "question_text": "Question?",
                "answer_text": "Answer",
                "score": 4,
                "round": 0,
                "feedback": "Good explanation of basics.",
            },
        ),
    )
    merged = SessionEvaluationAggregator.merge(theory, None)

    with patch(
        "app.interview.services.session_evaluator.TheoryEvaluatorService.evaluate_interview",
        new_callable=AsyncMock,
        side_effect=ValueError(
            "AI returned invalid JSON: Expecting value: line 1 column 1"
        ),
    ):
        result = await SessionEvaluatorService.evaluate_session(
            merged,
            provider=FakeProvider([]),
            locale="en",
            sources_text="Python / junior / basics",
        )

    assert "Good explanation of basics." in result.overall_feedback
    assert result.score_breakdown == {}

    completed = attach_session_score_breakdown(result, merged)
    assert completed.score_breakdown["theory"]["score"] == 4
