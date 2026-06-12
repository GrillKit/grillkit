# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for audio answer AI evaluation."""

import pytest

from app.ai.audio_probe import minimal_wav_bytes
from app.theory.services.evaluator.prompts import format_expected_rubric
from app.theory.services.evaluator.service import TheoryEvaluatorService
from tests.fakes import FakeProvider, answer_evaluation_json, follow_up_evaluation_json


def test_format_expected_rubric_empty() -> None:
    """Empty rubric renders as (none)."""
    assert format_expected_rubric(()) == "(none)"
    assert format_expected_rubric(None) == "(none)"


def test_format_expected_rubric_bullets() -> None:
    """Rubric bullets render as a markdown list."""
    text = format_expected_rubric(("First point", "Second point"))
    assert text == "- First point\n- Second point"


def test_format_answer_evaluation_user_text_labels_candidate_content() -> None:
    """Evaluation prompt separates context from candidate answer."""
    text = TheoryEvaluatorService._format_answer_evaluation_user_text(
        question_text="What is a list?",
        question_code="items = []",
        answer_text="A mutable sequence.",
        expected_points=("Ordered", "Mutable"),
    )
    assert "Question (for context only, NOT part of the answer):" in text
    assert "Expected rubric points (checklist only, NOT candidate content):" in text
    assert "Candidate answer (evaluate this only):" in text
    assert "A mutable sequence." in text
    assert "- Ordered" in text
    assert "items = []" in text


@pytest.mark.asyncio
async def test_evaluate_with_audio_initial_round() -> None:
    """Round 0 audio evaluation uses the answer evaluation schema."""
    provider = FakeProvider(
        replies=[
            answer_evaluation_json(
                score=4,
                feedback="Clear spoken answer.",
                follow_up_needed=True,
                follow_up_question="Can you elaborate?",
            )
        ]
    )
    audio_wav = minimal_wav_bytes()

    (
        evaluation,
        follow_up_needed,
        follow_up_text,
    ) = await TheoryEvaluatorService.evaluate_submission(
        provider=provider,
        locale="en",
        answer_round=0,
        question_text="What is a generator?",
        question_code=None,
        initial_question_text="What is a generator?",
        initial_answer_text="",
        audio_wav=audio_wav,
    )

    assert evaluation.score == 4
    assert evaluation.feedback == "Clear spoken answer."
    assert follow_up_needed is True
    assert follow_up_text == "Can you elaborate?"


@pytest.mark.asyncio
async def test_evaluate_with_audio_follow_up_round() -> None:
    """Follow-up audio evaluation respects MAX_FOLLOW_UP_DEPTH."""
    provider = FakeProvider(
        replies=[
            follow_up_evaluation_json(
                score=3,
                feedback="Acceptable follow-up.",
                needs_further_follow_up=True,
                follow_up_question="One more detail?",
            )
        ]
    )
    audio_wav = minimal_wav_bytes()

    (
        evaluation,
        follow_up_needed,
        follow_up_text,
    ) = await TheoryEvaluatorService.evaluate_submission(
        provider=provider,
        locale="en",
        answer_round=TheoryEvaluatorService.MAX_FOLLOW_UP_DEPTH,
        question_text="Can you give an example?",
        question_code=None,
        initial_question_text="What is a generator?",
        initial_answer_text="It yields values lazily.",
        audio_wav=audio_wav,
    )

    assert evaluation.score == 3
    assert follow_up_needed is False
    assert follow_up_text == "One more detail?"
