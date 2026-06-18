# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for QuestionVoiceStatusService."""

from unittest.mock import patch

from app.platform.services.config import AppConfig
from app.question_voice.schemas import PiperVoiceStatusRead
from app.question_voice.services.status import QuestionVoiceStatusService


class TestResolveTtsTarget:
    """Tests for resolve_tts_target."""

    def test_defaults_when_no_config_no_overrides(self):
        """No config and no overrides use default locale and voice."""
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(None)
        assert voice_id == "en_US-lessac-medium"
        assert locale == "en"

    def test_uses_config_when_present(self):
        """Saved config determines voice and locale."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="ru",
            tts_voice_id="ru_RU-dmitri-medium",
        )
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(config)
        assert voice_id == "ru_RU-dmitri-medium"
        assert locale == "ru"

    def test_locale_override_takes_precedence(self):
        """Query locale overrides saved config locale and voice."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            tts_voice_id="en_US-lessac-medium",
        )
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(
            config, locale="de"
        )
        assert locale == "de"
        assert voice_id == "de_DE-thorsten-medium"

    def test_voice_id_override_takes_precedence(self):
        """Query voice_id overrides all other sources."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            tts_voice_id="en_US-lessac-medium",
        )
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(
            config, voice_id="fr_FR-siwis-medium"
        )
        assert voice_id == "fr_FR-siwis-medium"
        assert locale == "en"

    def test_locale_and_voice_id_override_together(self):
        """Both query params override saved config."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            tts_voice_id="en_US-lessac-medium",
        )
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(
            config, locale="es", voice_id="es_ES-davefx-medium"
        )
        assert voice_id == "es_ES-davefx-medium"
        assert locale == "es"

    def test_defaults_with_only_locale_override(self):
        """No config but locale override sets voice by locale."""
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(
            None, locale="fr"
        )
        assert voice_id == "fr_FR-siwis-medium"
        assert locale == "fr"

    def test_defaults_with_only_voice_id_override(self):
        """No config but voice_id override uses that voice and default locale."""
        voice_id, locale = QuestionVoiceStatusService.resolve_tts_target(
            None, voice_id="de_DE-thorsten-medium"
        )
        assert voice_id == "de_DE-thorsten-medium"
        assert locale == "en"


class TestResolveForConfig:
    """Tests for resolve_for_config."""

    def test_returns_status_and_enabled_true(self):
        """Enabled config returns status and True."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
        )
        ready = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="ready",
            percent=100,
            message="Ready",
            voice_display_name="Lessac (US English, medium)",
        )
        with patch(
            "app.question_voice.services.status.PiperVoiceService.get_status",
            return_value=ready,
        ):
            status, enabled = QuestionVoiceStatusService.resolve_for_config(config)
        assert status.state == "ready"
        assert enabled is True

    def test_returns_status_and_enabled_false(self):
        """Disabled config returns status and False."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
            question_voice_enabled=False,
        )
        missing = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="missing",
            percent=0,
            message="Not installed",
            voice_display_name="Lessac (US English, medium)",
        )
        with patch(
            "app.question_voice.services.status.PiperVoiceService.get_status",
            return_value=missing,
        ):
            status, enabled = QuestionVoiceStatusService.resolve_for_config(config)
        assert status.state == "missing"
        assert enabled is False

    def test_no_config_returns_default_and_false(self):
        """No config returns default voice status and disabled."""
        missing = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="missing",
            percent=0,
            message="Not installed",
            voice_display_name="Lessac (US English, medium)",
        )
        with patch(
            "app.question_voice.services.status.PiperVoiceService.get_status",
            return_value=missing,
        ):
            status, enabled = QuestionVoiceStatusService.resolve_for_config(None)
        assert enabled is False


class TestApiPayload:
    """Tests for api_payload."""

    def test_serializes_status_with_enabled_true(self):
        """Enabled flag is added to payload."""
        status = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="ready",
            percent=100,
            message="Ready",
            voice_display_name="Lessac (US English, medium)",
            loaded_in_memory=True,
        )
        payload = QuestionVoiceStatusService.api_payload(status, enabled=True)
        assert payload["state"] == "ready"
        assert payload["enabled"] is True
        assert payload["loaded_in_memory"] is True

    def test_replaces_missing_with_unavailable_when_disabled(self):
        """Missing state becomes unavailable when voice is disabled."""
        status = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="missing",
            percent=0,
            message="Not installed",
            voice_display_name="Lessac (US English, medium)",
        )
        payload = QuestionVoiceStatusService.api_payload(status, enabled=False)
        assert payload["state"] == "unavailable"
        assert payload["enabled"] is False

    def test_preserves_missing_when_enabled(self):
        """Missing state stays missing when voice is enabled."""
        status = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="missing",
            percent=0,
            message="Not installed",
            voice_display_name="Lessac (US English, medium)",
        )
        payload = QuestionVoiceStatusService.api_payload(status, enabled=True)
        assert payload["state"] == "missing"

    def test_preserves_non_missing_states_when_disabled(self):
        """Non-missing states are unchanged even when disabled."""
        for state in ("ready", "downloading", "error"):
            status = PiperVoiceStatusRead(
                voice_id="en_US-lessac-medium",
                locale="en",
                locale_label="English",
                state=state,
                percent=50,
                message="Progress",
                voice_display_name="Lessac (US English, medium)",
            )
            payload = QuestionVoiceStatusService.api_payload(status, enabled=False)
            assert payload["state"] == state
