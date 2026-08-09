# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Resolve section narrative feedback from cache or per-task fallbacks."""

from __future__ import annotations

from typing import Any


def resolve_section_feedback(
    cached: dict[str, Any] | None,
    items: tuple[dict[str, Any], ...],
    *,
    item_id_key: str,
) -> dict[str, Any]:
    """Return cached section feedback or synthesize it from per-task rows.

    Args:
        cached: Persisted section feedback payload, if any.
        items: Per-task evaluation rows for the section.
        item_id_key: Field name for the task or question identifier.

    Returns:
        Section feedback dict with narrative fields and score breakdown.
    """
    if cached:
        return cached

    feedback_texts = [
        str(item["feedback"]).strip() for item in items if item.get("feedback")
    ]
    section_feedback = (
        " ".join(feedback_texts) if feedback_texts else "Section complete."
    )

    question_rows: dict[str, dict[str, int]] = {}
    for item in items:
        item_id = str(item.get(item_id_key, "?"))
        round_num = int(item.get("round", 0))
        key = item_id if round_num == 0 else f"{item_id}:r{round_num}"
        score = item.get("score")
        question_rows[key] = {
            "score": score if isinstance(score, int) else 0,
            "max": 5,
        }

    return {
        "section_feedback": section_feedback,
        "topics_to_review": [],
        "strengths_summary": [],
        "score_breakdown": question_rows,
    }
