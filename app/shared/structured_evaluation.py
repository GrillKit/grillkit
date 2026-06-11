# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared structured LLM evaluation helpers."""

from __future__ import annotations

from pydantic import BaseModel

from app.ai.base import AIProvider, Message


async def evaluate_with_schema[T: BaseModel](
    provider: AIProvider,
    *,
    locale: str,
    instructions: str,
    response_model: type[T],
    user_text: str,
    audio_wav: bytes | None = None,
    max_tokens: int = 1000,
) -> T:
    """Run a structured evaluation via text or multimodal generation.

    Args:
        provider: Configured AI provider instance.
        locale: Locale for AI feedback.
        instructions: Evaluator instruction template constant.
        response_model: Pydantic model for parsed JSON output.
        user_text: User message text (full content for text mode; context for audio).
        audio_wav: Optional WAV bytes for multimodal evaluation.
        max_tokens: Maximum tokens for the model response.

    Returns:
        Parsed evaluation model instance.

    Raises:
        ValueError: If AI response is invalid or connection fails.
    """
    from app.theory.services.evaluator.prompts import (
        build_evaluator_instructions,
        build_prompt_with_schema,
        parse_json_response,
    )

    system_prompt = build_prompt_with_schema(
        build_evaluator_instructions(locale, instructions),
        response_model,
    )
    messages = [Message(role="system", content=system_prompt)]
    if audio_wav is not None:
        result = await provider.generate_with_audio(
            messages=messages,
            audio_wav=audio_wav,
            user_text=user_text,
            temperature=0.3,
            max_tokens=max_tokens,
        )
    else:
        messages.append(Message(role="user", content=user_text))
        result = await provider.generate(
            messages=messages,
            temperature=0.3,
            max_tokens=max_tokens,
        )
    content = result.content.strip()
    if not content:
        raise ValueError("AI returned empty response")
    return parse_json_response(content, response_model)
