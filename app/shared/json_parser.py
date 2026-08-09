# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared JSON parsing and schema helpers for AI structured evaluation."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

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
        "Keep string fields concise so the JSON fits in one response "
        "(feedback at most 4 sentences; follow-up questions one sentence).\n"
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
