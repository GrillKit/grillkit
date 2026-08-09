# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Abstract base class and capability protocols for AI providers.

This module defines the base abstractions and data models for AI providers,
including message structures, generation results, and capability-based
provider interfaces (ISP).
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
    """Base text-generation provider interface.

    All providers must implement at least text-based generation and lifecycle
    methods.  Streaming and audio are opt-in via separate capability protocols.
    """

    def __init__(self, model: str, **kwargs: object) -> None:
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

    @abstractmethod
    async def validate(self) -> bool:
        """Validate API key and connection."""

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate a single response."""

    @abstractmethod
    async def close(self) -> None:
        """Close the provider and release resources."""


class StreamingProvider(ABC):
    """Capability protocol for providers that support token streaming."""

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""

    @abstractmethod
    def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[str]:
        """Stream response tokens.

        Yields:
            Chunks of generated text as they become available.
        """


class AudioCapableProvider(ABC):
    """Capability protocol for providers that accept multimodal audio input."""

    @abstractmethod
    async def generate_with_audio(
        self,
        messages: list[Message],
        audio_wav: bytes,
        *,
        user_text: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate a response from system messages, user text, and audio."""

    @abstractmethod
    async def probe_audio_input(self, audio_wav: bytes) -> bool:
        """Probe whether the endpoint accepts multimodal audio input.

        Args:
            audio_wav: Canonical WAV bytes (mono PCM).

        Returns:
            True when the provider accepts the audio probe request.
        """
