# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Localized feedback strings for interview services."""

from app.shared.locales import TIMEOUT_FEEDBACK_MESSAGES, localized_string


def timeout_feedback_for_locale(locale: str) -> str:
    """Return user-facing feedback text for a timed-out answer round.

    Args:
        locale: Interview locale code (e.g. ``en``, ``ru``).

    Returns:
        Short feedback string shown to the user.
    """
    return localized_string(locale, TIMEOUT_FEEDBACK_MESSAGES)
