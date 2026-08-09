# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared timed-task mixin for theory and coding rounds."""

from __future__ import annotations

from datetime import datetime

from app.shared.task_timer import (
    DEFAULT_TIMEOUT_GRACE_SECONDS,
)
from app.shared.task_timer import (
    is_timer_expired as shared_is_timer_expired,
)
from app.shared.task_timer import (
    remaining_seconds as shared_remaining_seconds,
)
from app.shared.task_timer import (
    timer_deadline as shared_timer_deadline,
)


class TimedTask:
    """Mixin base for a task round that supports a per-task timer.

    Subclasses must declare ``id``, ``started_at``, and ``created_at``
    fields with compatible types, and may override ``TIMEOUT_GRACE_SECONDS``.
    """

    TIMEOUT_GRACE_SECONDS: int = DEFAULT_TIMEOUT_GRACE_SECONDS

    def timer_deadline(self, limit_seconds: int) -> datetime:
        """Compute the absolute deadline for this timed task round.

        Args:
            limit_seconds: Allowed duration in seconds.

        Returns:
            Timezone-aware deadline timestamp.

        Raises:
            ValueError: If the round has no ``started_at`` timestamp.
        """
        if self.started_at is None:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            raise ValueError(f"{self.__class__.__name__} round has no started_at")
        return shared_timer_deadline(
            self.started_at,  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            limit_seconds,
            label=self.__class__.__name__,
        )

    def is_timer_expired(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
        *,
        grace_seconds: int = TIMEOUT_GRACE_SECONDS,
    ) -> bool:
        """Return whether the per-task timer has elapsed.

        Args:
            limit_seconds: Configured limit for the section (None disables timer).
            now: Current time (defaults to UTC now).
            grace_seconds: Extra seconds allowed for network delay on timeout submit.

        Returns:
            True if the timer is enabled and the deadline plus grace has passed.
        """
        return shared_is_timer_expired(
            self.started_at,  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            limit_seconds,
            now,
            grace_seconds=grace_seconds,
        )

    def remaining_seconds(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
    ) -> int | None:
        """Return whole seconds left on the timer, or None if disabled.

        Args:
            limit_seconds: Configured limit for the section.
            now: Current time (defaults to UTC now).

        Returns:
            Non-negative seconds remaining, or None when the timer is off.
        """
        return shared_remaining_seconds(
            self.started_at,  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            limit_seconds,
            now,
        )

    def client_timeout_due(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a client-sent timeout should be accepted."""
        if limit_seconds is None or self.started_at is None:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            return False
        rem = self.remaining_seconds(limit_seconds, now)
        return self.is_timer_expired(limit_seconds, now, grace_seconds=0) or (
            rem is not None and rem <= 0
        )
