# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for AI provider base classes."""

import pytest
from abc import ABC

from app.ai.base import Message, GenerationResult, AIProvider


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test creating a Message instance."""
        msg = Message(role="user", content="Hello, AI!")
        assert msg.role == "user"
        assert msg.content == "Hello, AI!"

    def test_message_system_role(self):
        """Test creating a system message."""
        msg = Message(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    def test_message_assistant_role(self):
        """Test creating an assistant message."""
        msg = Message(role="assistant", content="How can I help?")
        assert msg.role == "assistant"
        assert msg.content == "How can I help?"


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_result_creation_full(self):
        """Test creating a complete GenerationResult."""
        result = GenerationResult(
            content="Test response",
            tokens_used=15,
            finish_reason="stop",
        )
        assert result.content == "Test response"
        assert result.tokens_used == 15
        assert result.finish_reason == "stop"

    def test_result_creation_minimal(self):
        """Test creating a minimal GenerationResult with defaults."""
        result = GenerationResult(content="Test response")
        assert result.content == "Test response"
        assert result.tokens_used is None
        assert result.finish_reason is None

    def test_result_creation_with_tokens(self):
        """Test creating a GenerationResult with only tokens."""
        result = GenerationResult(content="Test", tokens_used=10)
        assert result.content == "Test"
        assert result.tokens_used == 10
        assert result.finish_reason is None


class TestAIProvider:
    """Tests for AIProvider abstract base class."""

    def test_is_abstract_class(self):
        """Test that AIProvider is an abstract class."""
        assert issubclass(AIProvider, ABC)

    def test_init_sets_model(self):
        """Test that __init__ sets the model attribute."""
        # Create a concrete implementation for testing
        class ConcreteProvider(AIProvider):
            @property
            def name(self):
                return "Test"

            def supports_streaming(self):
                return True

            async def validate(self):
                return True

            async def generate(self, messages, temperature=0.7, max_tokens=2000):
                return GenerationResult("test")

            async def generate_stream(self, messages, temperature=0.7, max_tokens=2000):
                yield "test"

        provider = ConcreteProvider(model="gpt-4")
        assert provider.model == "gpt-4"

    def test_init_sets_config(self):
        """Test that __init__ stores additional kwargs in config."""
        class ConcreteProvider(AIProvider):
            @property
            def name(self):
                return "Test"

            def supports_streaming(self):
                return True

            async def validate(self):
                return True

            async def generate(self, messages, temperature=0.7, max_tokens=2000):
                return GenerationResult("test")

            async def generate_stream(self, messages, temperature=0.7, max_tokens=2000):
                yield "test"

        provider = ConcreteProvider(
            model="gpt-4",
            base_url="http://localhost",
            timeout=30.0,
        )
        assert provider.config["base_url"] == "http://localhost"
        assert provider.config["timeout"] == 30.0
