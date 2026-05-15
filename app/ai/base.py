# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Abstract base class for AI providers.

This module defines the base abstractions and data models for AI providers,
including message structures, generation results, and the abstract provider interface.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class Message:
    """A chat message for AI generation.

    Attributes:
        role: The message role (e.g., "system", "user", "assistant").
        content: The message text content.
    """

    role: str
    content: str


@dataclass
class GenerationResult:
    """Result of a generation request.

    Attributes:
        content: The generated text content.
        tokens_used: Total tokens consumed (None if unavailable).
        finish_reason: Reason for generation completion (None if unavailable).
    """

    content: str
    tokens_used: int | None = None
    finish_reason: str | None = None


class AIProvider(ABC):
    """Abstract base for all AI providers.

    This class defines the interface that all AI providers must implement,
    including generation, streaming, validation, and metadata.

    Attributes:
        model: The model name/identifier to use.
        config: Additional provider-specific configuration.
    """

    def __init__(self, model: str, **kwargs):
        """Initialize the provider.

        Args:
            model: The model name to use.
            **kwargs: Additional provider-specific configuration options.
        """
        self.model = model
        self.config = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        pass

    @abstractmethod
    async def validate(self) -> bool:
        """Validate API key and connection."""
        pass

    @abstractmethod
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
            ValueError: If the request fails or parameters are invalid.
        """
        pass

    @abstractmethod
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
            ValueError: If the request fails or parameters are invalid.
        """
        pass
