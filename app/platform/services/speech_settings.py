# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Narrow settings views for speech and question-voice runtimes."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.platform.services.config import ProviderConfig


@dataclass(frozen=True)
class SpeechSettings:
    """Whisper dictation settings from provider configuration.

    Attributes:
        speech_model_size: Whisper model size identifier.
        locale: Interview locale for transcription language.
    """

    speech_model_size: str
    locale: str


@dataclass(frozen=True)
class QuestionVoiceSettings:
    """Piper question-voice settings from provider configuration.

    Attributes:
        enabled: Whether question TTS is enabled.
        voice_id: Piper voice identifier.
        locale: Interview locale for status messaging.
    """

    enabled: bool
    voice_id: str
    locale: str


def speech_settings_from_config(config: "ProviderConfig") -> SpeechSettings:
    """Extract Whisper settings from a provider configuration.

    Args:
        config: Saved or submitted provider configuration.

    Returns:
        Speech runtime settings.
    """
    return SpeechSettings(
        speech_model_size=config.speech_model_size,
        locale=config.locale,
    )


def question_voice_settings_from_config(
    config: "ProviderConfig",
) -> QuestionVoiceSettings:
    """Extract Piper settings from a provider configuration.

    Args:
        config: Saved or submitted provider configuration.

    Returns:
        Question-voice runtime settings.
    """
    return QuestionVoiceSettings(
        enabled=config.question_voice_enabled,
        voice_id=config.tts_voice_id,
        locale=config.locale,
    )
