# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Per-round question timer helpers for interview services."""

from datetime import UTC, datetime, timedelta

from app.shared.locales import TIMEOUT_FEEDBACK_MESSAGES, localized_string

TIME_EXPIRED_ANSWER_TEXT = "[Time expired]"

TIMEOUT_GRACE_SECONDS = 2


def deadline(started_at: datetime, limit_seconds: int) -> datetime:
    """Compute the absolute deadline for a timed answer round.

    Args:
        started_at: When the round became active.
        limit_seconds: Allowed duration in seconds.

    Returns:
        Timezone-aware deadline timestamp.
    """
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    return started_at + timedelta(seconds=limit_seconds)


def is_expired(
    started_at: datetime | None,
    limit_seconds: int | None,
    now: datetime | None = None,
    *,
    grace_seconds: int = TIMEOUT_GRACE_SECONDS,
) -> bool:
    """Return whether the per-round timer has elapsed.

    Args:
        started_at: When the round became active.
        limit_seconds: Configured limit for the session (None disables timer).
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
    return now >= deadline(started_at, limit_seconds) + timedelta(seconds=grace_seconds)


def remaining_seconds(
    started_at: datetime | None,
    limit_seconds: int | None,
    now: datetime | None = None,
) -> int | None:
    """Return whole seconds left on the timer, or None if disabled.

    Args:
        started_at: When the round became active.
        limit_seconds: Configured limit for the session.
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
    end = deadline(started_at, limit_seconds)
    delta = (end - now).total_seconds()
    return max(0, int(delta))


def client_timeout_due(
    started_at: datetime | None,
    limit_seconds: int | None,
    now: datetime | None = None,
) -> bool:
    """Return whether a client-sent timeout should be accepted.

    Accepts when the hard deadline has passed or the UI would show zero seconds
    remaining (floor), so a ``00:00`` display is not rejected while sub-second
    time remains on the server clock.

    Args:
        started_at: When the round became active.
        limit_seconds: Configured limit for the session.
        now: Current time (defaults to UTC now).

    Returns:
        True when the round timer has effectively expired for the client.
    """
    if limit_seconds is None or started_at is None:
        return False
    rem = remaining_seconds(started_at, limit_seconds, now)
    return is_expired(started_at, limit_seconds, now, grace_seconds=0) or (
        rem is not None and rem <= 0
    )


def timeout_feedback(locale: str) -> str:
    """Localized feedback text for a timed-out answer.

    Args:
        locale: Interview locale code (e.g. ``en``, ``ru``).

    Returns:
        Short feedback string shown to the user.
    """
    return localized_string(locale, TIMEOUT_FEEDBACK_MESSAGES)
