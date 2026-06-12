# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for section feedback fallback resolution."""

from app.interview.services.section_feedback import resolve_section_feedback


def test_resolve_section_feedback_returns_cached_payload() -> None:
    """Cached section feedback is returned unchanged."""
    cached = {
        "section_feedback": "Cached narrative.",
        "topics_to_review": ["loops"],
        "strengths_summary": ["clarity"],
    }
    result = resolve_section_feedback(
        cached,
        (),
        item_id_key="question_id",
    )
    assert result == cached


def test_resolve_section_feedback_builds_fallback_from_task_rows() -> None:
    """Missing cached feedback is synthesized from per-task feedback rows."""
    result = resolve_section_feedback(
        None,
        (
            {
                "task_id": "cod-001",
                "round": 0,
                "score": 4,
                "feedback": "Good solution.",
            },
            {
                "task_id": "cod-001",
                "round": 1,
                "score": 3,
                "feedback": "Follow-up was weak.",
            },
        ),
        item_id_key="task_id",
    )
    assert "Good solution." in result["section_feedback"]
    assert "Follow-up was weak." in result["section_feedback"]
    assert result["score_breakdown"]["cod-001"]["score"] == 4
    assert result["score_breakdown"]["cod-001:r1"]["score"] == 3
