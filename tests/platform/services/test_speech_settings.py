# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for speech settings extraction from configuration."""

from dataclasses import FrozenInstanceError

import pytest

from app.platform.services.config import AppConfig
from app.platform.services.speech_settings import (
    QuestionVoiceSettings,
    SpeechSettings,
    question_voice_settings_from_config,
    speech_settings_from_config,
)


class TestSpeechSettings:
    """Tests for speech_settings_from_config."""

    def test_extracts_whisper_settings(self):
        """speech_settings_from_config yields size and locale."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            speech_model_size="medium",
            locale="ru",
        )
        settings = speech_settings_from_config(config)
        assert settings == SpeechSettings(
            speech_model_size="medium",
            locale="ru",
        )

    def test_uses_defaults_from_config(self):
        """Default config values are extracted correctly."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
        )
        settings = speech_settings_from_config(config)
        assert settings.speech_model_size == "small"
        assert settings.locale == "en"

    def test_speech_settings_is_frozen(self):
        """SpeechSettings dataclass is immutable."""
        settings = SpeechSettings(speech_model_size="small", locale="en")
        with pytest.raises(FrozenInstanceError):
            settings.speech_model_size = "large"


class TestQuestionVoiceSettings:
    """Tests for question_voice_settings_from_config."""

    def test_extracts_piper_settings(self):
        """question_voice_settings_from_config yields enabled, voice_id, locale."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="ru_RU-dmitri-medium",
            locale="ru",
        )
        settings = question_voice_settings_from_config(config)
        assert settings == QuestionVoiceSettings(
            enabled=True,
            voice_id="ru_RU-dmitri-medium",
            locale="ru",
        )

    def test_disabled_voice(self):
        """Disabled voice sets enabled flag to False."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )
        settings = question_voice_settings_from_config(config)
        assert settings.enabled is False
        assert settings.voice_id == "en_US-lessac-medium"
        assert settings.locale == "en"

    def test_question_voice_settings_is_frozen(self):
        """QuestionVoiceSettings dataclass is immutable."""
        settings = QuestionVoiceSettings(
            enabled=True,
            voice_id="en_US-lessac-medium",
            locale="en",
        )
        with pytest.raises(FrozenInstanceError):
            settings.enabled = False

    def test_question_voice_settings_is_frozen_for_voice_id(self):
        """Mutating voice_id on QuestionVoiceSettings raises error."""
        settings = QuestionVoiceSettings(
            enabled=True,
            voice_id="en_US-lessac-medium",
            locale="en",
        )
        with pytest.raises(FrozenInstanceError):
            settings.voice_id = "ru_RU-dmitri-medium"

    def test_question_voice_settings_is_frozen_for_locale(self):
        """Mutating locale on QuestionVoiceSettings raises error."""
        settings = QuestionVoiceSettings(
            enabled=True,
            voice_id="en_US-lessac-medium",
            locale="en",
        )
        with pytest.raises(FrozenInstanceError):
            settings.locale = "fr"

    def test_defaults_from_config(self):
        """Default config yields default voice settings."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
        )
        settings = question_voice_settings_from_config(config)
        assert settings.enabled is False
        assert settings.voice_id == "en_US-lessac-medium"
        assert settings.locale == "en"
