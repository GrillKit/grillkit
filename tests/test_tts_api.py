# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TTS status and question-audio API endpoints."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.interview.services.creation import InterviewCreationService
from app.interview.services.query import InterviewQuery
from app.platform.services.config import AppConfig
from app.question_voice.schemas import PiperVoiceStatusRead


@pytest.fixture
def voice_config(minimal_app_config):
    """Provider config with question voice enabled."""
    return replace(
        minimal_app_config,
        locale="en",
        question_voice_enabled=True,
    )


class TestTtsStatusApi:
    """Tests for GET /speech/tts/status."""

    def test_status_json_when_voice_disabled(self, client):
        """Status reports unavailable when voice is off."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
        )
        missing = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="missing",
            percent=0,
            message="Question voice is not installed.",
            voice_display_name="Lessac (US English, medium)",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.question_voice.services.piper_voice.PiperVoiceService.get_status",
                return_value=missing,
            ),
        ):
            response = client.get(
                "/speech/tts/status",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "unavailable"
        assert payload["enabled"] is False

    def test_status_json_when_voice_ready(self, client, voice_config):
        """Status reports ready when the Piper voice is installed."""
        ready = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="ready",
            percent=100,
            message="Question voice ready for English.",
            voice_display_name="Lessac (US English, medium)",
            loaded_in_memory=True,
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=voice_config,
            ),
            patch(
                "app.question_voice.services.piper_voice.PiperVoiceService.get_status",
                return_value=ready,
            ),
        ):
            response = client.get(
                "/speech/tts/status",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "ready"
        assert payload["enabled"] is True

    def test_status_locale_query_overrides_saved_config(self, client, voice_config):
        """Status endpoint honors locale query param over saved config on Configuration."""
        missing = PiperVoiceStatusRead(
            voice_id="ru_RU-dmitri-medium",
            locale="ru",
            locale_label="Russian",
            state="missing",
            percent=0,
            message="Question voice is not installed.",
            voice_display_name="Dmitri (Russian, medium)",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=voice_config,
            ),
            patch(
                "app.question_voice.services.piper_voice.PiperVoiceService.get_status",
                return_value=missing,
            ) as get_status,
        ):
            response = client.get(
                "/speech/tts/status?locale=ru",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["voice_id"] == "ru_RU-dmitri-medium"
        assert payload["locale"] == "ru"
        get_status.assert_called_once_with("ru_RU-dmitri-medium", "ru")

    def test_voice_download_without_config_uses_defaults(self, client):
        """Download schedules work before provider config is saved."""
        ready = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="downloading",
            percent=5,
            message="Downloading question voice…",
            voice_display_name="Lessac (US English, medium)",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch(
                "app.question_voice.services.piper_voice.PiperVoiceService.start_download",
                new_callable=AsyncMock,
                return_value=ready,
            ),
        ):
            response = client.post(
                "/speech/tts/voice/download",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "downloading"
        assert payload["enabled"] is False

    def test_voice_download_schedules_work(self, client, voice_config):
        """Download returns status after scheduling Piper voice install."""
        ready = PiperVoiceStatusRead(
            voice_id="en_US-lessac-medium",
            locale="en",
            locale_label="English",
            state="downloading",
            percent=5,
            message="Downloading question voice…",
            voice_display_name="Lessac (US English, medium)",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=voice_config,
            ),
            patch(
                "app.question_voice.services.piper_voice.PiperVoiceService.start_download",
                new_callable=AsyncMock,
                return_value=ready,
            ),
        ):
            response = client.post(
                "/speech/tts/voice/download",
                headers={"Accept": "application/json"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["state"] == "downloading"
        assert payload["enabled"] is True


class TestQuestionAudioApi:
    """Tests for GET /interview/{id}/question-audio."""

    def test_question_audio_requires_voice_enabled(
        self, client, isolated_db, temp_questions_dir, monkeypatch
    ):
        """Disabled voice returns 404."""
        del temp_questions_dir
        monkeypatch.setattr("random.shuffle", lambda items: None)
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
        )
        from app.interview.domain.value_objects import (
            InterviewSelection,
            TrackSelection,
        )

        interview = InterviewCreationService.create_interview(
            selection=InterviewSelection(
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("data-structures",),
                    ),
                )
            ),
            locale="en",
            question_count=1,
        )
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=config,
        ):
            response = client.get(f"/interview/{interview.id}/question-audio")
        assert response.status_code == 404

    def test_question_audio_streams_cached_wav(
        self,
        client,
        isolated_db,
        temp_questions_dir,
        monkeypatch,
        tmp_path,
        voice_config,
    ):
        """Enabled voice returns WAV from cache when available."""
        del temp_questions_dir
        monkeypatch.setattr("random.shuffle", lambda items: None)
        from app.interview.domain.value_objects import (
            InterviewSelection,
            TrackSelection,
        )

        interview = InterviewCreationService.create_interview(
            selection=InterviewSelection(
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("data-structures",),
                    ),
                )
            ),
            locale="en",
            question_count=1,
        )
        reloaded = InterviewQuery.get_interview(interview.id)
        assert reloaded is not None
        answer = reloaded.answers[0]
        wav_path = tmp_path / "question.wav"
        wav_path.write_bytes(b"RIFF")

        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=voice_config,
            ),
            patch(
                "app.question_voice.services.question_audio.TtsCacheService.get_or_fetch",
                new_callable=AsyncMock,
                return_value=Path(wav_path),
            ),
        ):
            response = client.get(
                f"/interview/{interview.id}/question-audio",
                params={"answer_id": answer.id},
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/wav")
        assert response.content == b"RIFF"
