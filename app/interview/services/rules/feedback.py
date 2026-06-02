# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Parsing helpers for persisted interview feedback fields."""

import json
from typing import Any


def parse_overall_feedback(raw: str | None) -> dict[str, Any] | None:
    """Parse ``overall_feedback`` JSON from the database.

    Args:
        raw: JSON string stored on the interview row.

    Returns:
        Parsed dict, or None if the session has no feedback.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"overall_feedback": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"overall_feedback": raw}
