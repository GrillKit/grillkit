# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for OpenAI-compatible AI provider."""

from unittest.mock import AsyncMock, MagicMock, patch

from openai import AuthenticationError, OpenAIError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage
import pytest

from app.ai.base import Message
from app.ai.openai_compatible import OpenAICompatibleProvider


class TestOpenAICompatibleProvider:
    """Tests for OpenAICompatibleProvider class."""

    @pytest.fixture
    def mock_openai_client(self):
        """Fixture to mock AsyncOpenAI client at module level."""
        with patch("app.ai.openai_compatible.AsyncOpenAI") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            yield mock_client, mock_instance

    def test_init(self, mock_openai_client):
        """Test provider initialization."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model",
            base_url="http://localhost",
            api_key="test-key",
            timeout=5.0,
        )
        assert provider.model == "test-model"
        mock_client.assert_called_once_with(
            base_url="http://localhost",
            api_key="test-key",
            timeout=5.0,
        )

    def test_name_property(self, mock_openai_client):
        """Test name property returns correct display name."""
        provider = OpenAICompatibleProvider(model="gpt-4", base_url="http://localhost")
        assert provider.name == "OpenAI-Compatible (gpt-4)"

    def test_supports_streaming(self, mock_openai_client):
        """Test supports_streaming always returns True."""
        provider = OpenAICompatibleProvider(model="gpt-4", base_url="http://localhost")
        assert provider.supports_streaming() is True

    def test_format_messages(self, mock_openai_client):
        """Test _format_messages converts messages correctly."""
        provider = OpenAICompatibleProvider(model="gpt-4", base_url="http://localhost")
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        formatted = provider._format_messages(messages)
        expected = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        assert formatted == expected

    @pytest.mark.asyncio
    async def test_generate_success(self, mock_openai_client):
        """Test successful generation of a single response."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_chat_completion = ChatCompletion(
            id="chatcmpl-123",
            choices=[
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": ChatCompletionMessage(
                        content="Test response", role="assistant"
                    ),
                    "logprobs": None,
                }
            ],
            created=1678886400,
            model="test-model",
            object="chat.completion",
            usage=CompletionUsage(completion_tokens=3, prompt_tokens=2, total_tokens=5),
        )
        mock_instance.chat.completions.create.return_value = mock_chat_completion

        messages = [Message(role="user", content="Prompt")]
        result = await provider.generate(messages)

        mock_instance.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=provider._format_messages(messages),
            temperature=0.7,
            max_tokens=2000,
            stream=False,
        )
        assert result.content == "Test response"
        assert result.tokens_used == 5
        assert result.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_authentication_error(self, mock_openai_client):
        """Test generate handles AuthenticationError."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_response = MagicMock()
        mock_response.request = MagicMock()
        mock_instance.chat.completions.create.side_effect = AuthenticationError(
            "Invalid Key", response=mock_response, body=None
        )

        messages = [Message(role="user", content="Prompt")]
        with pytest.raises(ValueError, match="Invalid API key"):
            await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_rate_limit_error(self, mock_openai_client):
        """Test generate handles RateLimitError."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_response = MagicMock()
        mock_response.request = MagicMock()
        mock_instance.chat.completions.create.side_effect = RateLimitError(
            "Rate Limit", response=mock_response, body=None
        )

        messages = [Message(role="user", content="Prompt")]
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_openai_error(self, mock_openai_client):
        """Test generate handles generic OpenAIError."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_instance.chat.completions.create.side_effect = OpenAIError("API Error")

        messages = [Message(role="user", content="Prompt")]
        with pytest.raises(ValueError, match="API error: API Error"):
            await provider.generate(messages)

    @pytest.mark.asyncio
    async def test_generate_stream_success(self, mock_openai_client):
        """Test successful streaming of response tokens."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        # Create proper mock objects for streaming chunks
        def create_mock_chunk(content):
            delta = MagicMock()
            delta.content = content
            choice = MagicMock()
            choice.delta = delta
            chunk = MagicMock()
            chunk.choices = [choice]
            return chunk

        async def mock_stream_response():
            yield create_mock_chunk("Chunk1")
            yield create_mock_chunk("Chunk2")
            yield create_mock_chunk("Chunk3")

        mock_instance.chat.completions.create.return_value = mock_stream_response()

        messages = [Message(role="user", content="Prompt")]
        chunks = []
        async for chunk in provider.generate_stream(messages):
            chunks.append(chunk)

        mock_instance.chat.completions.create.assert_called_once_with(
            model="test-model",
            messages=provider._format_messages(messages),
            temperature=0.7,
            max_tokens=2000,
            stream=True,
        )
        assert chunks == ["Chunk1", "Chunk2", "Chunk3"]

    @pytest.mark.asyncio
    async def test_generate_stream_authentication_error(self, mock_openai_client):
        """Test stream generation handles AuthenticationError."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_response = MagicMock()
        mock_response.request = MagicMock()
        mock_instance.chat.completions.create.side_effect = AuthenticationError(
            "Invalid Key", response=mock_response, body=None
        )

        messages = [Message(role="user", content="Prompt")]
        with pytest.raises(ValueError, match="Invalid API key"):
            async for _ in provider.generate_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_generate_stream_rate_limit_error(self, mock_openai_client):
        """Test stream generation handles RateLimitError."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_response = MagicMock()
        mock_response.request = MagicMock()
        mock_instance.chat.completions.create.side_effect = RateLimitError(
            "Rate Limit", response=mock_response, body=None
        )

        messages = [Message(role="user", content="Prompt")]
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            async for _ in provider.generate_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_generate_stream_openai_error(self, mock_openai_client):
        """Test stream generation handles generic OpenAIError."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_instance.chat.completions.create.side_effect = OpenAIError("API Error")

        messages = [Message(role="user", content="Prompt")]
        with pytest.raises(ValueError, match="API error: API Error"):
            async for _ in provider.generate_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_generate_with_audio_success(self, mock_openai_client):
        """Test successful multimodal generation with attached WAV."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_chat_completion = ChatCompletion(
            id="chatcmpl-audio",
            choices=[
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": ChatCompletionMessage(
                        content='{"score":4,"feedback":"ok","follow_up_needed":false}',
                        role="assistant",
                    ),
                    "logprobs": None,
                }
            ],
            created=1678886400,
            model="test-model",
            object="chat.completion",
            usage=CompletionUsage(completion_tokens=3, prompt_tokens=2, total_tokens=5),
        )
        mock_instance.chat.completions.create.return_value = mock_chat_completion

        from app.ai.audio_probe import minimal_wav_bytes

        messages = [Message(role="system", content="Evaluate the answer.")]
        result = await provider.generate_with_audio(
            messages=messages,
            audio_wav=minimal_wav_bytes(),
            user_text="Question:\nWhat is Python?",
            temperature=0.3,
            max_tokens=1000,
        )

        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "test-model"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 1000
        user_message = call_kwargs["messages"][-1]
        assert user_message["role"] == "user"
        assert isinstance(user_message["content"], list)
        assert user_message["content"][0]["type"] == "text"
        assert user_message["content"][1]["type"] == "input_audio"
        assert result.content.startswith('{"score":4')

    @pytest.mark.asyncio
    async def test_validate_success(self, mock_openai_client):
        """Test successful API key validation."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_instance.models.list.return_value = AsyncMock()
        is_valid = await provider.validate()
        mock_instance.models.list.assert_called_once()
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_failure(self, mock_openai_client):
        """Test failed API key validation."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        mock_instance.models.list.side_effect = OpenAIError("Invalid Key")
        is_valid = await provider.validate()
        mock_instance.models.list.assert_called_once()
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_close(self, mock_openai_client):
        """Test close method calls client.close()."""
        mock_client, mock_instance = mock_openai_client
        provider = OpenAICompatibleProvider(
            model="test-model", base_url="http://localhost"
        )

        await provider.close()
        mock_instance.close.assert_called_once()
