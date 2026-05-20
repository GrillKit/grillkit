# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview evaluator JSON parsing helpers."""

import json

import pytest

from app.services.interview_evaluator import (
    InterviewEvaluation,
)
from app.services.interview_evaluator_prompts import (
    looks_like_json_schema_fragment,
    parse_json_response,
)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "object", "description": "Final evaluation of the interview"},
        {"type": "string", "description": "Feedback text"},
        {
            "type": "object",
            "properties": {
                "overall_feedback": {"type": "string"},
            },
            "required": ["overall_feedback"],
        },
        {"$schema": "https://json-schema.org/draft/2020-12/schema"},
    ],
)
def test_looks_like_json_schema_fragment_detects_schema(payload: dict) -> None:
    """Schema-shaped payloads are flagged before Pydantic validation."""
    assert looks_like_json_schema_fragment(payload) is True


@pytest.mark.parametrize(
    "payload",
    [
        {
            "overall_feedback": "Solid performance overall.",
            "topics_to_review": ["asyncio"],
            "strengths_summary": ["clarity"],
            "score_breakdown": {"q1": {"score": 4, "max": 5}},
        },
        {"score": 4, "feedback": "Good answer", "follow_up_needed": False},
    ],
)
def test_looks_like_json_schema_fragment_allows_data(payload: dict) -> None:
    """Real evaluation payloads are not mistaken for schema metadata."""
    assert looks_like_json_schema_fragment(payload) is False


def test_parse_json_response_rejects_schema_fragment() -> None:
    """Parsing raises a clear error when the model returns schema metadata."""
    content = json.dumps(
        {"type": "object", "description": "Final evaluation of the interview"}
    )
    with pytest.raises(ValueError, match="JSON Schema metadata"):
        parse_json_response(content, InterviewEvaluation)


def test_parse_json_response_accepts_valid_evaluation() -> None:
    """Valid session evaluation JSON is parsed and validated."""
    content = json.dumps(
        {
            "overall_feedback": "Well done.",
            "topics_to_review": [],
            "strengths_summary": ["basics"],
            "score_breakdown": {},
        }
    )
    result = parse_json_response(content, InterviewEvaluation)
    assert result.overall_feedback == "Well done."
