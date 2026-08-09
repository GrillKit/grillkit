# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared structured LLM evaluation helpers."""

from collections.abc import AsyncIterator
import json

import pytest

from app.ai.base import AIProvider, GenerationResult, Message
from app.shared.structured_evaluation import generate_and_parse_json_response
from app.theory.domain.evaluator_models import AnswerEvaluation


class _SequencedGenerateProvider(AIProvider):
    """Minimal provider stub that returns preset generation results."""

    def __init__(self, results: list[GenerationResult]) -> None:
        super().__init__("test-model")
        self._results = list(results)
        self.calls = 0
        self.max_tokens_history: list[int] = []

    @property
    def name(self) -> str:
        return "Test Provider"

    def supports_streaming(self) -> bool:
        return False

    async def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        yield ""

    async def validate(self) -> bool:
        return True

    async def probe_audio_input(self, audio_wav: bytes) -> bool:
        return False

    async def generate_with_audio(
        self,
        messages: list[Message],
        audio_wav: bytes,
        *,
        user_text: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        raise NotImplementedError

    async def close(self) -> None:
        pass

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
