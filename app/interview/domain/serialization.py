# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persistence serialization for interview domain value objects."""

from __future__ import annotations

import json
from typing import Any

from app.interview.domain.value_objects import (
    InterviewSelection,
    SectionBranchSpec,
    SessionMode,
    SessionSelection,
    TrackSelection,
)

SESSION_SPEC_VERSION = 2

_SESSION_MODES: frozenset[str] = frozenset(
    {
        "theory_only",
        "coding_only",
        "theory_then_coding",
        "coding_then_theory",
    }
)


def _sources_to_payload(sources: tuple[TrackSelection, ...]) -> list[dict[str, object]]:
    """Serialize track selections for JSON persistence.

    Args:
        sources: Ordered track selections.

    Returns:
        List of JSON-compatible source dicts.
    """
    return [
        {
            "track": source.track,
            "level": source.level,
            "categories": list(source.categories),
        }
        for source in sources
    ]


def _branch_to_payload(branch: SectionBranchSpec) -> dict[str, object]:
    """Serialize one section branch for JSON persistence.

    Args:
        branch: Theory or coding branch configuration.

    Returns:
        JSON-compatible branch dict.
    """
    return {
        "enabled": branch.enabled,
        "question_count": branch.question_count,
        "task_time_limit_seconds": branch.task_time_limit_seconds,
        "sources": _sources_to_payload(branch.sources),
    }


def selection_to_spec(selection: InterviewSelection) -> str:
    """Serialize theory sources to JSON for ``theory_sections.selection_spec``.

    Args:
        selection: Theory-only interview selection.

    Returns:
        JSON string with a ``sources`` list.
    """
    payload = {"sources": _sources_to_payload(selection.sources)}
    return json.dumps(payload, separators=(",", ":"))


def session_to_spec(session: SessionSelection) -> str:
    """Serialize a session selection to JSON for ``Interview.selection_spec``.

    Args:
        session: Full session selection including mode and branches.

    Returns:
        JSON string in selection_spec v2 format.
    """
    payload = {
        "version": SESSION_SPEC_VERSION,
        "session_mode": session.session_mode,
        "exclude_known": session.exclude_known,
        "theory": _branch_to_payload(session.theory),
        "coding": _branch_to_payload(session.coding),
    }
    return json.dumps(payload, separators=(",", ":"))


def selection_from_payload(data: dict[str, Any]) -> InterviewSelection:
    """Build ``InterviewSelection`` from a JSON-compatible dict.

    Args:
        data: Dict with ``sources`` list.

    Returns:
        InterviewSelection instance.

    Raises:
        ValueError: If payload shape is invalid.
    """
    sources_raw = data.get("sources")
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ValueError("Invalid selection_spec: missing sources")

    sources: list[TrackSelection] = []
    for item in sources_raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid selection_spec: source must be an object")
        track = item.get("track")
        level = item.get("level")
        categories = item.get("categories")
        if not isinstance(track, str) or not isinstance(level, str):
            raise ValueError("Invalid selection_spec: track and level required")
        if not isinstance(categories, list) or not categories:
            raise ValueError("Invalid selection_spec: categories required")
        sources.append(
            TrackSelection(
                track=track,
                level=level,
                categories=tuple(str(category) for category in categories),
            )
        )
    return InterviewSelection(sources=tuple(sources))


def _parse_branch_payload(
    data: dict[str, Any],
    *,
    branch_name: str,
    default_enabled: bool,
) -> SectionBranchSpec:
    """Parse one section branch from a v2 selection payload.

    Args:
        data: Branch object from JSON.
        branch_name: Branch key for error messages.
        default_enabled: Enabled flag when omitted from JSON.

    Returns:
        Parsed section branch spec.

    Raises:
        ValueError: If branch payload shape is invalid.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Invalid selection_spec: {branch_name} must be an object")

    enabled = data.get("enabled", default_enabled)
    if not isinstance(enabled, bool):
        raise ValueError(
            f"Invalid selection_spec: {branch_name}.enabled must be boolean"
        )

    question_count = data.get("question_count", 0)
    if not isinstance(question_count, int):
        raise ValueError(
            f"Invalid selection_spec: {branch_name}.question_count must be integer"
        )

    timer = data.get("task_time_limit_seconds")
    if timer is not None and not isinstance(timer, int):
        raise ValueError(
            f"Invalid selection_spec: {branch_name}.task_time_limit_seconds invalid"
        )

    sources_payload = data.get("sources", [])
    if not isinstance(sources_payload, list):
        raise ValueError(
            f"Invalid selection_spec: {branch_name}.sources must be a list"
        )

    if sources_payload:
        sources = selection_from_payload({"sources": sources_payload}).sources
    else:
        sources = ()

    return SectionBranchSpec(
        enabled=enabled,
        question_count=question_count,
        task_time_limit_seconds=timer,
        sources=sources,
    )


def _branch_enabled_for_mode(mode: SessionMode, branch: str) -> bool:
    """Derive whether a branch is enabled from the session mode.

    Args:
        mode: Session mode from setup.
        branch: ``"theory"`` or ``"coding"``.

    Returns:
        True when the branch participates in the session mode.
    """
    if mode == "theory_only":
        return branch == "theory"
    if mode == "coding_only":
        return branch == "coding"
    return True


def _normalize_session_selection(session: SessionSelection) -> SessionSelection:
    """Align branch ``enabled`` flags with ``session_mode``.

    Args:
        session: Parsed session selection.

    Returns:
        Session selection with consistent enabled flags.
    """
    theory_enabled = _branch_enabled_for_mode(session.session_mode, "theory")
    coding_enabled = _branch_enabled_for_mode(session.session_mode, "coding")
    if (
        session.theory.enabled == theory_enabled
        and session.coding.enabled == coding_enabled
    ):
        return session
    return SessionSelection(
        session_mode=session.session_mode,
        exclude_known=session.exclude_known,
        theory=SectionBranchSpec(
            enabled=theory_enabled,
            question_count=session.theory.question_count,
            task_time_limit_seconds=session.theory.task_time_limit_seconds,
            sources=session.theory.sources,
        ),
        coding=SectionBranchSpec(
            enabled=coding_enabled,
            question_count=session.coding.question_count,
            task_time_limit_seconds=session.coding.task_time_limit_seconds,
            sources=session.coding.sources,
        ),
    )


def session_from_payload(
    data: dict[str, Any],
    *,
    question_count: int = 5,
    task_time_limit_seconds: int | None = None,
) -> SessionSelection:
    """Build ``SessionSelection`` from a JSON-compatible dict.

    Supports v2 payloads and legacy v1 ``{sources: [...]}`` rows.

    Args:
        data: Parsed selection_spec JSON object.
        question_count: Fallback theory question count for legacy v1 rows.
        task_time_limit_seconds: Fallback timer for legacy v1 rows.

    Returns:
        Normalized session selection.

    Raises:
        ValueError: If payload shape is invalid.
    """
    if data.get("version") == SESSION_SPEC_VERSION or (
        "session_mode" in data and "theory" in data
    ):
        session_mode = data.get("session_mode")
        if not isinstance(session_mode, str) or session_mode not in _SESSION_MODES:
            raise ValueError("Invalid selection_spec: session_mode required")
        exclude_known = data.get("exclude_known", True)
        if not isinstance(exclude_known, bool):
            raise ValueError("Invalid selection_spec: exclude_known must be boolean")
        theory_raw = data.get("theory")
        coding_raw = data.get("coding")
        if not isinstance(theory_raw, dict) or not isinstance(coding_raw, dict):
            raise ValueError("Invalid selection_spec: theory and coding required")
        session = SessionSelection(
            session_mode=session_mode,  # type: ignore[arg-type]
            exclude_known=exclude_known,
            theory=_parse_branch_payload(
                theory_raw,
                branch_name="theory",
                default_enabled=_branch_enabled_for_mode(session_mode, "theory"),  # type: ignore[arg-type]
            ),
            coding=_parse_branch_payload(
                coding_raw,
                branch_name="coding",
                default_enabled=_branch_enabled_for_mode(session_mode, "coding"),  # type: ignore[arg-type]
            ),
        )
        return _normalize_session_selection(session)

    interview_selection = selection_from_payload(data)
    return SessionSelection.theory_only(
        sources=interview_selection.sources,
        question_count=question_count,
        task_time_limit_seconds=task_time_limit_seconds,
    )


def parse_selection_spec(raw: str) -> InterviewSelection:
    """Parse theory sources from ``selection_spec`` JSON.

    Args:
        raw: JSON string stored on a theory section or legacy interview row.

    Returns:
        Parsed theory-only selection.

    Raises:
        ValueError: If ``raw`` is empty or invalid.
    """
    if not raw:
        raise ValueError("selection_spec is empty")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("selection_spec must be a JSON object")
    if data.get("version") == SESSION_SPEC_VERSION or (
        "session_mode" in data and "theory" in data
    ):
        session = session_from_payload(data)
        return session.theory_selection
    return selection_from_payload(data)


def parse_coding_selection_spec(raw: str) -> InterviewSelection:
    """Parse coding sources from a section ``selection_spec`` JSON.

    Args:
        raw: JSON string stored on a coding section row.

    Returns:
        Parsed coding branch selection.

    Raises:
        ValueError: If ``raw`` is empty or invalid.
    """
    if not raw:
        raise ValueError("selection_spec is empty")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("selection_spec must be a JSON object")
    if data.get("version") == SESSION_SPEC_VERSION or (
        "session_mode" in data and "coding" in data
    ):
        session = session_from_payload(data)
        return session.coding_selection
    return selection_from_payload(data)


def parse_session_spec(
    raw: str,
    *,
    question_count: int = 5,
    task_time_limit_seconds: int | None = None,
) -> SessionSelection:
    """Parse full session selection from ``selection_spec`` JSON.

    Args:
        raw: JSON string stored on ``Interview.selection_spec``.
        question_count: Fallback theory question count for legacy v1 rows.
        task_time_limit_seconds: Fallback timer for legacy v1 rows.

    Returns:
        Parsed session selection.

    Raises:
        ValueError: If ``raw`` is empty or invalid.
    """
    if not raw:
        raise ValueError("selection_spec is empty")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("selection_spec must be a JSON object")
    return session_from_payload(
        data,
        question_count=question_count,
        task_time_limit_seconds=task_time_limit_seconds,
    )


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
