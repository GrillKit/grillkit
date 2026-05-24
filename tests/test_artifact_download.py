# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared artifact download state."""

from app.question_voice.services.piper_voice import PiperVoiceService
from app.speech.services.whisper_model import WhisperModelService


def test_whisper_and_piper_have_separate_download_state():
    """Whisper and Piper must not share download lock or active key."""
    WhisperModelService.reset_download_state()
    PiperVoiceService.reset_download_state()

    assert WhisperModelService._download_lock is not PiperVoiceService._download_lock

    WhisperModelService._active_key = "small"
    WhisperModelService._percent = 42

    assert WhisperModelService.is_downloading("small")
    assert not PiperVoiceService.is_downloading("small")
    assert PiperVoiceService.download_percent() == 0

    WhisperModelService.reset_download_state()
    PiperVoiceService.reset_download_state()
