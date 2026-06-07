# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for localized interview feedback helpers."""

from app.interview.services.rules.feedback import timeout_feedback_for_locale


def test_timeout_feedback_localized() -> None:
    """timeout_feedback_for_locale returns a non-empty string for known locales."""
    assert timeout_feedback_for_locale("en")
    assert timeout_feedback_for_locale("ru")
