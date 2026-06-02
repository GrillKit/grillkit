# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for per-round question timer behavior on Answer."""

from datetime import UTC, datetime, timedelta

from app.interview.domain.entities import Answer, Interview


def _answer(started_at: datetime | None) -> Answer:
    """Build a minimal domain answer with a timer start time."""
    base = started_at or datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    return Answer(
        id=1,
        interview_id="s1",
        question_id="q1",
        order=1,
        round=0,
        question_text="Q1",
        question_code=None,
        answer_text=None,
        score=None,
        feedback=None,
        started_at=started_at,
        created_at=base,
    )


def test_timer_deadline_adds_limit_seconds() -> None:
    """Deadline is started_at plus the configured limit."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    assert _answer(started).timer_deadline(120) == started + timedelta(seconds=120)


def test_is_timer_expired_false_when_timer_disabled() -> None:
    """Missing limit means the round is never expired."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    now = started + timedelta(hours=1)
    assert not _answer(started).is_timer_expired(None, now)


def test_is_timer_expired_with_grace() -> None:
    """Expiry includes grace seconds beyond the hard deadline."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    limit = 60
    just_before_grace = started + timedelta(
        seconds=limit + Answer.TIMEOUT_GRACE_SECONDS - 1
    )
    assert not _answer(started).is_timer_expired(limit, just_before_grace)
    after_grace = started + timedelta(seconds=limit + Answer.TIMEOUT_GRACE_SECONDS)
    assert _answer(started).is_timer_expired(limit, after_grace)


def test_remaining_seconds_counts_down() -> None:
    """remaining_seconds returns floored whole seconds left."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    now = started + timedelta(seconds=30)
    assert _answer(started).remaining_seconds(120, now) == 90


def test_client_timeout_due_when_display_zero() -> None:
    """client_timeout_due accepts when UI would show 00:00."""
    started = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
    limit = 60
    now = started + timedelta(seconds=59, milliseconds=500)
    assert _answer(started).client_timeout_due(limit, now)


def test_timeout_feedback_localized() -> None:
    """timeout_feedback returns a non-empty string for known locales."""
    assert Interview.timeout_feedback("en")
    assert Interview.timeout_feedback("ru")


def test_time_expired_constant() -> None:
    """TIME_EXPIRED_ANSWER_TEXT is the persisted timeout marker."""
    assert Answer.TIME_EXPIRED_ANSWER_TEXT == "[Time expired]"
