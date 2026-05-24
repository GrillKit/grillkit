# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Config read helpers for other features' service layers."""

from dataclasses import dataclass

from app.platform.services.config import ConfigService


@dataclass(frozen=True)
class QuestionVoiceSettings:
    """Resolved question-voice settings from ``data/config.json``."""

    voice_id: str


def get_question_voice_settings() -> QuestionVoiceSettings | None:
    """Return TTS settings when question voice is enabled in config.

    Returns:
        Voice id and related settings, or None when disabled or config is missing.
    """
    config = ConfigService.get_config()
    if config is None or not config.question_voice_enabled:
        return None
    return QuestionVoiceSettings(voice_id=config.tts_voice_id)
