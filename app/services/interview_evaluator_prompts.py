# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Prompt templates and JSON-schema helpers for interview AI evaluation."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.domain.locales import language_instruction

_JSON_SCHEMA_TYPE_NAMES = frozenset(
    {"object", "string", "array", "integer", "number", "boolean", "null"}
)

_JSON_SCHEMA_METADATA_KEYS = frozenset(
    {
        "$schema",
        "$ref",
        "additionalProperties",
        "allOf",
        "anyOf",
        "definitions",
        "description",
        "enum",
        "format",
        "items",
        "oneOf",
        "properties",
        "required",
        "title",
        "type",
    }
)

DICTATION_TRANSCRIPT_NOTE = """Answers may be typed or dictated with speech-to-text. Dictated text can
contain recognition errors, garbled words, or odd spelling. Judge technical
understanding and substance only — do not lower scores for grammar, wording,
or speech-to-text artifacts when the intended meaning is reasonably clear."""

ANSWER_EVALUATION_INSTRUCTIONS = """You are a technical interviewer evaluating a candidate's answer.
Assess the answer based on:
- 5: Excellent — complete understanding, examples, edge cases considered
- 4: Good — solid understanding with minor omissions
- 3: Adequate — basic understanding but lacks depth
- 2: Weak — significant gaps in understanding
- 1: Poor — incorrect or no meaningful answer

If the answer scores 3 or below, set follow_up_needed to true and provide a
follow_up_question that probes deeper into the topic. Do not set follow_up_needed
if the answer is already comprehensive (score 4-5)."""

FOLLOW_UP_EVALUATION_INSTRUCTIONS = """You are a technical interviewer evaluating a candidate's follow-up answer.
You have the original question, the candidate's initial answer, the follow-up question,
and their follow-up answer. Evaluate the follow-up answer on a scale of 1-5:
- 5: Excellent — deep understanding, insightful
- 4: Good — solid follow-up
- 3: Adequate — acceptable but shallow
- 2: Weak — still not grasping the concept
- 1: Poor — unable to answer

If the follow-up scores 2 or below AND this is not the second follow-up,
you may set needs_further_follow_up to true with another question.
Otherwise set it to false."""

SESSION_EVALUATION_INSTRUCTIONS = """You are a technical interviewer providing a final evaluation.
Review all the question-answer pairs from the interview and provide:
1. Overall narrative feedback summarizing the candidate's performance
2. Topics they should review
3. Key strengths demonstrated
4. A per-question score breakdown

For score_breakdown, use question IDs as keys. Each value is an object
with "score" (sum of all rounds for that question) and "max" fields.

Return a JSON data object with your evaluation content. Do NOT return JSON Schema
metadata (no top-level "type", "properties", "description", or schema definitions).

Example response (fill with your own content):
{
  "overall_feedback": "The candidate demonstrated solid fundamentals...",
  "topics_to_review": ["asyncio", "memory management"],
  "strengths_summary": ["clear explanations", "good use of examples"],
  "score_breakdown": {
    "q1": {"score": 8, "max": 10},
    "q2": {"score": 5, "max": 10}
  }
}"""


def build_evaluator_instructions(locale: str, task_instructions: str) -> str:
    """Combine locale, dictation, and task-specific evaluator instructions.

    Args:
        locale: Supported interview locale code.
        task_instructions: Answer, follow-up, or session evaluation template.

    Returns:
        Full instruction block for the evaluator system prompt (before schema).
    """
    return (
        f"{language_instruction(locale)}\n\n"
        f"{DICTATION_TRANSCRIPT_NOTE}\n\n"
        f"{task_instructions}"
    )


def looks_like_json_schema_fragment(data: Any) -> bool:
    """Return True if parsed JSON looks like schema metadata, not instance data.

    Some models echo JSON Schema fragments (e.g. ``{"type": "object",
    "description": "..."}``) instead of filling the schema with values.

    Args:
        data: Parsed JSON value from the model response.

    Returns:
        True when the payload is likely a schema description, not data.
    """
    if not isinstance(data, dict):
        return False

    keys = frozenset(data.keys())
    if not keys:
        return False

    schema_markers = keys & {
        "$schema",
        "$ref",
        "properties",
        "required",
        "additionalProperties",
        "allOf",
        "anyOf",
        "oneOf",
        "items",
        "definitions",
    }
    if schema_markers:
        return True

    type_value = data.get("type")
    return (
        isinstance(type_value, str)
        and type_value in _JSON_SCHEMA_TYPE_NAMES
        and keys <= _JSON_SCHEMA_METADATA_KEYS
    )


def build_prompt_with_schema(instructions: str, model_class: type[BaseModel]) -> str:
    """Build a system prompt with the Pydantic model's JSON schema embedded.

    Args:
        instructions: Natural language instructions for the AI.
        model_class: Pydantic model class whose schema to embed.

    Returns:
        Complete system prompt string.
    """
    schema = model_class.model_json_schema()
    schema_str = json.dumps(schema, indent=2)
    return (
        f"{instructions}\n\n"
        "The JSON block below describes the REQUIRED SHAPE of your response only. "
        "Return a single JSON object with real field VALUES (scores, feedback text, "
        "lists, nested objects). "
        'Do NOT return JSON Schema metadata: no top-level "type", "properties", '
        '"required", "description", "$schema", or property-definition objects.\n\n'
        f"Required response shape (for reference — fill with data, do not echo):\n"
        f"{schema_str}\n\n"
        "Return ONLY one valid JSON object, no markdown fences, no extra text."
    )


def parse_json_response[T: BaseModel](content: str, model: type[T]) -> T:
    """Parse AI JSON response and validate against a Pydantic model.

    Strips optional markdown code fences before parsing.

    Args:
        content: Raw JSON string from the AI.
        model: Pydantic model class to validate against.

    Returns:
        Validated Pydantic model instance.

    Raises:
        ValueError: If JSON is invalid or doesn't match the model.
    """
    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {e}") from e

    if looks_like_json_schema_fragment(data):
        raise ValueError(
            "AI returned JSON Schema metadata instead of evaluation data "
            "(e.g. an object with only 'type' and 'description'). "
            "Return a data object with field values such as overall_feedback, "
            "not a schema definition."
        )

    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"AI response validation failed: {e}") from e
