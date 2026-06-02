# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Test doubles for AI and interview flows."""

from collections.abc import AsyncIterator

from app.ai.base import AIProvider, GenerationResult, Message
from app.interview.services.evaluator.models import AnswerEvaluation, FollowUpEvaluation


def answer_evaluation_json(
    *,
    score: int = 4,
    feedback: str = "Solid answer.",
    follow_up_needed: bool = False,
    follow_up_question: str | None = None,
) -> str:
    """Build JSON text matching ``AnswerEvaluation`` for a fake provider.

    Args:
        score: Rating 1-5.
        feedback: Evaluation feedback text.
        follow_up_needed: Whether a follow-up is requested.
        follow_up_question: Follow-up question when needed.

    Returns:
        Serialized JSON string.
    """
    payload = AnswerEvaluation(
        score=score,
        feedback=feedback,
        follow_up_needed=follow_up_needed,
        follow_up_question=follow_up_question,
    )
    return payload.model_dump_json()


def follow_up_evaluation_json(
    *,
    score: int = 3,
    feedback: str = "Acceptable follow-up.",
    needs_further_follow_up: bool = False,
    follow_up_question: str | None = None,
) -> str:
    """Build JSON text matching ``FollowUpEvaluation`` for a fake provider.

    Args:
        score: Rating 1-5.
        feedback: Evaluation feedback text.
        needs_further_follow_up: Whether another follow-up is requested.
        follow_up_question: Next follow-up question when needed.

    Returns:
        Serialized JSON string.
    """
    payload = FollowUpEvaluation(
        score=score,
        feedback=feedback,
        needs_further_follow_up=needs_further_follow_up,
        follow_up_question=follow_up_question,
    )
    return payload.model_dump_json()


class FakeProvider(AIProvider):
    """Deterministic AI provider that returns queued JSON responses.

    Attributes:
        replies: JSON strings returned in order from ``generate``.
    """

    def __init__(self, replies: list[str], model: str = "fake") -> None:
        """Initialize with a queue of response bodies.

        Args:
            replies: Content strings returned sequentially.
            model: Model name passed to the base class.
        """
        super().__init__(model=model)
        self._replies = list(replies)

    @property
    def name(self) -> str:
        """Provider display name."""
        return "fake"

    def supports_streaming(self) -> bool:
        """Whether streaming is supported."""
        return False

    async def validate(self) -> bool:
        """Always report a valid connection."""
        return True

    async def probe_audio_input(self, audio_wav: bytes) -> bool:
        """Report audio probe success for tests."""
        _ = audio_wav
        return True

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Return the next queued reply.

        Args:
            messages: Conversation messages (ignored).
            temperature: Sampling temperature (ignored).
            max_tokens: Token limit (ignored).

        Returns:
            Generation result with queued content.

        Raises:
            ValueError: If the reply queue is empty.
        """
        del messages, temperature, max_tokens
        if not self._replies:
            raise ValueError("FakeProvider has no more queued replies")
        return GenerationResult(content=self._replies.pop(0))

    async def generate_with_audio(
        self,
        messages: list[Message],
        audio_wav: bytes,
        *,
        user_text: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Return the next queued reply for audio evaluation tests.

        Args:
            messages: Conversation messages (ignored).
            audio_wav: Audio payload (ignored).
            user_text: User prompt text (ignored).
            temperature: Sampling temperature (ignored).
            max_tokens: Token limit (ignored).

        Returns:
            Generation result with queued content.

        Raises:
            ValueError: If the reply queue is empty.
        """
        del messages, audio_wav, user_text, temperature, max_tokens
        if not self._replies:
            raise ValueError("FakeProvider has no more queued replies")
        return GenerationResult(content=self._replies.pop(0))

    async def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Yield a single chunk from the queued reply.

        Args:
            messages: Conversation messages.
            temperature: Sampling temperature.
            max_tokens: Token limit.

        Yields:
            Full response content as one chunk.
        """
        result = await self.generate(messages, temperature, max_tokens)
        yield result.content

    async def close(self) -> None:
        """No-op close."""
