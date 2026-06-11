# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared per-task timer helpers for theory and coding rounds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

DEFAULT_TIMEOUT_GRACE_SECONDS = 2


def timer_deadline(
    started_at: datetime | None,
    limit_seconds: int,
    *,
    label: str = "Task",
) -> datetime:
    """Compute the absolute deadline for a timed task round.

    Args:
        started_at: When the round timer started.
        limit_seconds: Allowed duration in seconds.
        label: Entity label for error messages.

    Returns:
        Timezone-aware deadline timestamp.

    Raises:
        ValueError: If ``started_at`` is missing.
    """
    if started_at is None:
        raise ValueError(f"{label} round has no started_at")
    normalized = started_at
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=UTC)
    return normalized + timedelta(seconds=limit_seconds)


def is_timer_expired(
    started_at: datetime | None,
    limit_seconds: int | None,
    now: datetime | None = None,
    *,
    grace_seconds: int = DEFAULT_TIMEOUT_GRACE_SECONDS,
) -> bool:
    """Return whether a per-round timer has elapsed.

    Args:
        started_at: When the round timer started.
        limit_seconds: Configured limit (``None`` disables the timer).
        now: Current time (defaults to UTC now).
        grace_seconds: Extra seconds allowed for network delay on timeout submit.

    Returns:
        True if the timer is enabled and the deadline plus grace has passed.
    """
    if limit_seconds is None or started_at is None:
        return False
    if now is None:
        now = datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now >= timer_deadline(started_at, limit_seconds) + timedelta(
        seconds=grace_seconds
    )


def remaining_seconds(
    started_at: datetime | None,
    limit_seconds: int | None,
    now: datetime | None = None,
) -> int | None:
    """Return whole seconds left on the timer, or None if disabled.

    Args:
        started_at: When the round timer started.
        limit_seconds: Configured limit for the section.
        now: Current time (defaults to UTC now).

    Returns:
        Non-negative seconds remaining, or None when the timer is off.
    """
    if limit_seconds is None or started_at is None:
        return None
    if now is None:
        now = datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    end = timer_deadline(started_at, limit_seconds)
    delta = (end - now).total_seconds()
    return max(0, int(delta))
