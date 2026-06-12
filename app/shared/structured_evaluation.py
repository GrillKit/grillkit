# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared structured LLM evaluation helpers."""

from __future__ import annotations

from pydantic import BaseModel

from app.ai.base import AIProvider, GenerationResult, Message

_MAX_RETRY_TOKENS = 4096
_COMPACT_JSON_RETRY_NOTE = (
    "\n\nYour previous response was truncated or invalid JSON. "
    "Keep all string fields brief (feedback at most 4 sentences, "
    "follow-up questions one sentence). "
    "Return ONLY one complete valid JSON object, no markdown fences."
)


def _should_retry_structured_parse(
    exc: ValueError,
    finish_reason: str | None,
) -> bool:
    """Return True when a structured JSON parse failure may succeed on retry.

    Args:
        exc: Parse or validation error from the model response.
        finish_reason: Provider completion reason, when available.

    Returns:
        True if the caller should retry with a higher token budget.
    """
    if finish_reason == "length":
        return True
    return "invalid JSON" in str(exc)


async def _parse_generation_result[T: BaseModel](
    result: GenerationResult,
    response_model: type[T],
) -> T:
    """Parse one provider result into a validated structured model.

    Args:
        result: Raw provider generation result.
        response_model: Pydantic model for parsed JSON output.

    Returns:
        Parsed evaluation model instance.

    Raises:
        ValueError: If the response body is empty or invalid JSON.
    """
    from app.theory.services.evaluator.prompts import parse_json_response

    content = result.content.strip()
    if not content:
        raise ValueError("AI returned empty response")
    return parse_json_response(content, response_model)


async def generate_and_parse_json_response[T: BaseModel](
    provider: AIProvider,
    *,
    messages: list[Message],
    response_model: type[T],
    max_tokens: int = 2000,
    temperature: float = 0.1,
) -> T:
    """Generate JSON from chat messages and parse it with retry on truncation.

    Args:
        provider: Configured AI provider instance.
        messages: Full chat messages for the provider request.
        response_model: Pydantic model for parsed JSON output.
        max_tokens: Initial maximum tokens for the model response.
        temperature: Sampling temperature for generation.

    Returns:
        Parsed evaluation model instance.

    Raises:
        ValueError: If AI response is invalid or connection fails after retries.
    """
    token_budgets = [max_tokens, min(max_tokens * 2, _MAX_RETRY_TOKENS)]
    last_error: ValueError | None = None
    base_system_prompt = (
        messages[0].content if messages and messages[0].role == "system" else None
    )

    for attempt, budget in enumerate(token_budgets):
        attempt_messages = list(messages)
        if attempt > 0 and base_system_prompt is not None:
            attempt_messages[0] = Message(
                role="system",
                content=base_system_prompt + _COMPACT_JSON_RETRY_NOTE,
            )

        result = await provider.generate(
            messages=attempt_messages,
            temperature=temperature,
            max_tokens=budget,
        )

        try:
            return await _parse_generation_result(result, response_model)
        except ValueError as exc:
            last_error = exc
            if attempt < len(token_budgets) - 1 and _should_retry_structured_parse(
                exc, result.finish_reason
            ):
                continue
            raise

    if last_error is not None:
        raise last_error
    raise ValueError("AI returned empty response")


async def evaluate_with_schema[T: BaseModel](
    provider: AIProvider,
    *,
    locale: str,
    instructions: str,
    response_model: type[T],
    user_text: str,
    audio_wav: bytes | None = None,
    max_tokens: int = 2000,
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
    )

    system_prompt = build_prompt_with_schema(
        build_evaluator_instructions(locale, instructions),
        response_model,
    )
    token_budgets = [max_tokens, min(max_tokens * 2, _MAX_RETRY_TOKENS)]
    last_error: ValueError | None = None

    for attempt, budget in enumerate(token_budgets):
        prompt = system_prompt
        if attempt > 0:
            prompt = system_prompt + _COMPACT_JSON_RETRY_NOTE
        messages = [Message(role="system", content=prompt)]

        if audio_wav is not None:
            result = await provider.generate_with_audio(
                messages=messages,
                audio_wav=audio_wav,
                user_text=user_text,
                temperature=0.0,
                max_tokens=budget,
            )
        else:
            messages.append(Message(role="user", content=user_text))
            result = await provider.generate(
                messages=messages,
                temperature=0.0,
                max_tokens=budget,
            )

        try:
            return await _parse_generation_result(result, response_model)
        except ValueError as exc:
            last_error = exc
            if attempt < len(token_budgets) - 1 and _should_retry_structured_parse(
                exc, result.finish_reason
            ):
                continue
            raise

    if last_error is not None:
        raise last_error
    raise ValueError("AI returned empty response")
