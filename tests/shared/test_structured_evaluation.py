# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared structured LLM evaluation helpers."""

import json

import pytest

from app.ai.base import GenerationResult, Message
from app.shared.structured_evaluation import generate_and_parse_json_response
from app.theory.services.evaluator.models import AnswerEvaluation


class _SequencedGenerateProvider:
    """Minimal provider stub that returns preset generation results."""

    def __init__(self, results: list[GenerationResult]) -> None:
        self._results = list(results)
        self.calls = 0
        self.max_tokens_history: list[int] = []

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        del messages, temperature
        self.max_tokens_history.append(max_tokens)
        if self.calls >= len(self._results):
            raise ValueError("No more queued provider results")
        result = self._results[self.calls]
        self.calls += 1
        return result


@pytest.mark.asyncio
async def test_generate_and_parse_json_response_retries_truncated_json() -> None:
    """Invalid truncated JSON triggers one retry with a higher token budget."""
    valid_payload = json.dumps(
        {
            "score": 4,
            "feedback": "Solid answer with minor gaps.",
            "strengths": ["clear structure"],
            "weaknesses": ["missed edge cases"],
            "follow_up_needed": False,
            "follow_up_question": None,
        }
    )
    provider = _SequencedGenerateProvider(
        [
            GenerationResult(
                content='{"score": 4, "feedback": "Solid answer but cut off',
                finish_reason="length",
            ),
            GenerationResult(content=valid_payload, finish_reason="stop"),
        ]
    )
    messages = [
        Message(role="system", content="Evaluate the answer."),
        Message(role="user", content="Question and answer text."),
    ]

    result = await generate_and_parse_json_response(
        provider,
        messages=messages,
        response_model=AnswerEvaluation,
        max_tokens=1000,
    )

    assert result.score == 4
    assert provider.calls == 2
    assert provider.max_tokens_history == [1000, 2000]


@pytest.mark.asyncio
async def test_generate_and_parse_json_response_does_not_retry_validation_error() -> (
    None
):
    """Schema validation failures are not retried."""
    provider = _SequencedGenerateProvider(
        [
            GenerationResult(
                content=json.dumps({"score": 9, "feedback": "Too high"}),
                finish_reason="stop",
            ),
        ]
    )
    messages = [
        Message(role="system", content="Evaluate the answer."),
        Message(role="user", content="Question and answer text."),
    ]

    with pytest.raises(ValueError, match="validation failed"):
        await generate_and_parse_json_response(
            provider,
            messages=messages,
            response_model=AnswerEvaluation,
            max_tokens=1000,
        )

    assert provider.calls == 1
