# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for CodingEvaluatorService."""

import pytest

from app.coding.services.evaluator.service import CodingEvaluatorService
from tests.fakes import FakeProvider, coding_answer_evaluation_json


@pytest.mark.asyncio
async def test_evaluate_submission_uses_run_history_context() -> None:
    """Initial coding evaluation returns parsed score and follow-up decision."""
    provider = FakeProvider(
        replies=[
            coding_answer_evaluation_json(
                score=3,
                feedback="Needs better typing.",
                follow_up_needed=True,
                follow_up_question="Add type hints.",
                follow_up_mode="code",
            )
        ]
    )
    (
        evaluation,
        follow_up_needed,
        follow_up_text,
        follow_up_mode,
    ) = await CodingEvaluatorService.evaluate_submission(
        provider=provider,
        locale="en",
        answer_round=0,
        prompt_text="Add type hints to this function.",
        task_spec={"expected_points": ["Use list[int] syntax"]},
        source_code="def process(data):\n    return data",
        run_attempts=(
            {
                "attempt_no": 1,
                "status": "compile_error",
                "tests_passed": 0,
                "tests_total": 0,
            },
        ),
        submit_test_summary={"status": "success", "tests_passed": 0, "tests_total": 0},
    )
    assert evaluation.score == 3
    assert follow_up_needed is True
    assert follow_up_text == "Add type hints."
    assert follow_up_mode == "code"


@pytest.mark.asyncio
async def test_coding_evaluator_evaluate_section() -> None:
    """Coding section evaluation returns parsed section narrative."""
    from tests.fakes import FakeProvider, section_evaluation_json

    provider = FakeProvider(
        replies=[section_evaluation_json(section_feedback="Strong coding section.")]
    )
    result = await CodingEvaluatorService.evaluate_section(
        provider=provider,
        task_submissions=[
            {
                "task_id": "cod-001",
                "round": 0,
                "prompt_text": "Solve it.",
                "submitted_code": "return 1",
                "score": 4,
            }
        ],
        sources_text="Python / junior: basics",
        locale="en",
    )
    assert result.section_feedback == "Strong coding section."
