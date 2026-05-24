# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for per-round question timer domain rules."""

from datetime import UTC, datetime, timedelta

from app.interview.domain.timer import (
    TIME_EXPIRED_ANSWER_TEXT,
    client_timeout_due,
    deadline,
    is_expired,
    remaining_seconds,
    timeout_feedback,
)


def test_deadline_adds_limit_seconds() -> None:
    """Deadline is started_at plus the configured limit."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    assert deadline(started, 120) == started + timedelta(seconds=120)


def test_is_expired_false_when_timer_disabled() -> None:
    """Missing limit means the round is never expired."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    now = started + timedelta(hours=1)
    assert not is_expired(started, None, now)


def test_is_expired_with_grace() -> None:
    """Grace period delays expiry for client timeout messages."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    limit = 60
    at_deadline = started + timedelta(seconds=60)
    assert not is_expired(started, limit, at_deadline, grace_seconds=2)
    after_grace = started + timedelta(seconds=62)
    assert is_expired(started, limit, after_grace, grace_seconds=2)


def test_is_expired_without_grace_for_late_submit() -> None:
    """Late answer submit uses zero grace."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    limit = 60
    at_deadline = started + timedelta(seconds=60)
    assert is_expired(started, limit, at_deadline, grace_seconds=0)


def test_remaining_seconds_counts_down() -> None:
    """Remaining seconds never goes below zero."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    now = started + timedelta(seconds=45)
    assert remaining_seconds(started, 120, now) == 75


def test_client_timeout_due_when_display_shows_zero() -> None:
    """Client timeout is accepted when floored remaining seconds are zero."""
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    limit = 60
    at_subsecond_remaining = started + timedelta(seconds=59, milliseconds=500)
    assert not is_expired(started, limit, at_subsecond_remaining, grace_seconds=0)
    assert remaining_seconds(started, limit, at_subsecond_remaining) == 0
    assert client_timeout_due(started, limit, at_subsecond_remaining)


def test_timeout_feedback_localized() -> None:
    """Timeout feedback resolves via locale message tables."""
    assert "0" in timeout_feedback("en")
    assert "0" in timeout_feedback("ru")
    assert timeout_feedback("EN") == timeout_feedback("en")
    assert TIME_EXPIRED_ANSWER_TEXT == "[Time expired]"
