# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Exceptions for question-voice TTS services."""


class TtsDomainError(Exception):
    """Base class for TTS-related domain errors."""


class QuestionVoiceDisabledError(TtsDomainError):
    """Raised when question voice is disabled in configuration."""

    def __init__(self) -> None:
        """Initialize with a fixed message."""
        super().__init__("Question voice is disabled in configuration")


class QuestionVoiceSynthesisError(TtsDomainError):
    """Raised when the Piper voice is missing or synthesis fails."""

    def __init__(self, message: str) -> None:
        """Initialize with a user-facing detail.

        Args:
            message: Explanation for API consumers.
        """
        super().__init__(message)
