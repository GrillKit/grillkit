# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for audio answer AI evaluation."""

import pytest

from app.ai.audio_probe import minimal_wav_bytes
from app.interview.services.answer_ai_evaluation import AnswerAiEvaluationService
from app.interview.services.evaluator.service import InterviewEvaluatorService
from tests.fakes import FakeProvider, answer_evaluation_json, follow_up_evaluation_json


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
    ) = await AnswerAiEvaluationService.evaluate_with_audio(
        answer_round=0,
        question_text="What is a generator?",
        question_code=None,
        audio_wav=audio_wav,
        initial_question_text="What is a generator?",
        initial_answer_text="",
        provider=provider,
        locale="en",
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
    ) = await AnswerAiEvaluationService.evaluate_with_audio(
        answer_round=InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH,
        question_text="Can you give an example?",
        question_code=None,
        audio_wav=audio_wav,
        initial_question_text="What is a generator?",
        initial_answer_text="It yields values lazily.",
        provider=provider,
        locale="en",
    )

    assert evaluation.score == 3
    assert follow_up_needed is False
    assert follow_up_text == "One more detail?"
