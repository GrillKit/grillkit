# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""OpenAI-compatible provider adapter using official openai library.

This module provides an adapter for OpenAI-compatible APIs including
OpenAI, Grok, Ollama, vLLM, and other OpenAI-compatible endpoints.
"""

from typing import AsyncIterator

from openai import AsyncOpenAI, AuthenticationError, OpenAIError, RateLimitError
from openai.types.chat import ChatCompletionMessageParam

from .base import AIProvider, GenerationResult, Message


class OpenAICompatibleProvider(AIProvider):
    """Provider for any OpenAI-compatible API.

    Covers: OpenAI, Grok, Ollama, vLLM, and other OpenAI-compatible endpoints.

    Attributes:
        client: AsyncOpenAI client instance for API communication.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        **kwargs,
    ):
        """Initialize the OpenAI-compatible provider.

        Args:
            model: The model name to use.
            base_url: API endpoint URL.
            api_key: API key (optional for local providers).
            timeout: Request timeout in seconds.
            **kwargs: Additional provider-specific options.
        """
        super().__init__(model, **kwargs)
        # OpenAI library requires api_key, provide dummy for local providers
        effective_key = api_key if api_key else "not-needed"
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=effective_key,
            timeout=timeout,
        )

    @property
    def name(self) -> str:
        """Provider display name."""
        return f"OpenAI-Compatible ({self.model})"

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        return True

    def _format_messages(self, messages: list[Message]) -> list[ChatCompletionMessageParam]:
        """Convert Message objects to OpenAI format.

        Args:
            messages: List of Message objects.

        Returns:
            Formatted messages for OpenAI API.
        """
        return [{"role": msg.role, "content": msg.content} for msg in messages]  # type: ignore[return-value]

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate a single response.

        Args:
            messages: List of conversation messages.
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens to generate.

        Returns:
            The generation result with content and metadata.

        Raises:
            ValueError: If authentication fails, rate limit exceeded, or API error occurs.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
        except AuthenticationError as e:
            raise ValueError("Invalid API key") from e
        except RateLimitError as e:
            raise ValueError("Rate limit exceeded") from e
        except OpenAIError as e:
            raise ValueError(f"API error: {e}") from e

        choice = response.choices[0]
        content = choice.message.content or ""
        finish_reason = choice.finish_reason
        tokens_used = response.usage.total_tokens if response.usage else None

        return GenerationResult(
            content=content,
            tokens_used=tokens_used,
            finish_reason=finish_reason,
        )

    async def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Stream response tokens.

        Args:
            messages: List of conversation messages.
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens to generate.

        Yields:
            Chunks of generated text as they become available.

        Raises:
            ValueError: If authentication fails, rate limit exceeded, or API error occurs.
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except AuthenticationError as e:
            raise ValueError("Invalid API key") from e
        except RateLimitError as e:
            raise ValueError("Rate limit exceeded") from e
        except OpenAIError as e:
            raise ValueError(f"API error: {e}") from e

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def validate(self) -> bool:
        """Validate API key and connection.

        Returns:
            True if connection is valid, False otherwise.
        """
        try:
            await self.client.models.list()
            return True
        except OpenAIError:
            return False

    async def close(self) -> None:
        """Close the provider and release resources."""
        await self.client.close()
