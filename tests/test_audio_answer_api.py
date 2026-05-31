# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for POST /interview/{id}/audio-answer and related interview UI gating."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.audio_probe import minimal_wav_bytes
from app.ai.llm_models import LLMModelEntry
from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.page import InterviewPageService
from app.platform.services.config import AppConfig
from app.question_voice.schemas import QuestionVoicePageContext
from app.speech.schemas.page import SpeechModelPageContext
from app.speech.schemas.status import WhisperModelStatusRead
from tests.fakes import answer_evaluation_json
from tests.helpers.selection import minimal_selection_spec
from tests.test_audio_answer_processing import (
    FakeTranscriber,
    _seed_two_question_interview,
)


def _parse_ndjson(body: str) -> list[dict]:
    """Parse NDJSON response text into message dicts."""
    return [json.loads(line) for line in body.strip().split("\n") if line.strip()]


def _ready_speech_status() -> WhisperModelStatusRead:
    """Build a ready Whisper status snapshot for template tests."""
    return WhisperModelStatusRead(
        size="base",
        locale="en",
        locale_label="English",
        state="ready",
        percent=100,
        message="Speech model ready.",
        model_display_name="Whisper base",
        loaded_in_memory=True,
    )


def _speech_model_page_context() -> SpeechModelPageContext:
    """Build speech model page context for interview page tests."""
    status = _ready_speech_status()
    return SpeechModelPageContext(
        speech_model_status=status,
        speech_model_banner=False,
        status=status,
    )


def _question_voice_page_context() -> QuestionVoicePageContext:
    """Build question-voice page context for interview page tests."""
    return QuestionVoicePageContext(
        tts_voice_status=None,
        tts_voice_banner=False,
    )


def _active_interview_read(interview_id: str) -> InterviewRead:
    """Build an active interview read model with one unanswered question."""
    return InterviewRead(
        id=interview_id,
        status="active",
        locale="en",
        selection_spec=minimal_selection_spec(categories=["basics"]),
        question_ids='["q1"]',
        question_count=1,
        question_time_limit_seconds=None,
        answers=[
            AnswerRead(
                id=1,
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
                question_code=None,
                answer_text=None,
                score=None,
                started_at=None,
            )
        ],
    )


@pytest.fixture
def audio_api_client(client, override_ws_ai_provider):
    """Test client with speech transcriber attached to app state."""
    override_ws_ai_provider(client, [])
    client.app.state.speech_transcriber = FakeTranscriber("spoken via api")
    yield client
    client.app.state.speech_transcriber = None


class TestAudioAnswerApi:
    """Tests for POST /interview/{id}/audio-answer."""

    def test_audio_answer_streams_ndjson_events(
        self, audio_api_client, isolated_db, override_ws_ai_provider, monkeypatch
    ):
        """Successful upload returns saved, evaluating, transcript, and feedback lines."""
        monkeypatch.setattr(
            "app.interview.services.answer_processing.AnswerProcessingService.require_audio_answer_enabled",
            staticmethod(lambda: None),
        )
        interview_id = _seed_two_question_interview("audio-api-1")
        override_ws_ai_provider(
            audio_api_client,
            [answer_evaluation_json(score=5, follow_up_needed=False)],
        )
        wav_bytes = minimal_wav_bytes(duration_sec=0.2)

        response = audio_api_client.post(
            f"/interview/{interview_id}/audio-answer",
            data={"question_id": "q1"},
            files={"file": ("answer.wav", wav_bytes, "audio/wav")},
        )

        assert response.status_code == 200
        assert "application/x-ndjson" in response.headers.get("content-type", "")
        messages = _parse_ndjson(response.text)
        assert [message["type"] for message in messages] == [
            "saved",
            "evaluating",
            "transcript",
            "feedback",
        ]
        assert messages[2]["text"] == "spoken via api"
        assert messages[3]["question_id"] == "q1"

    def test_audio_answer_rejects_invalid_wav(
        self, audio_api_client, isolated_db, monkeypatch
    ):
        """Invalid WAV payloads return HTTP 400 before streaming."""
        monkeypatch.setattr(
            "app.interview.services.answer_processing.AnswerProcessingService.require_audio_answer_enabled",
            staticmethod(lambda: None),
        )
        interview_id = _seed_two_question_interview("audio-api-invalid")

        response = audio_api_client.post(
            f"/interview/{interview_id}/audio-answer",
            data={"question_id": "q1"},
            files={"file": ("answer.wav", b"not-wav", "audio/wav")},
        )

        assert response.status_code == 400
        assert "WAV" in response.json()["detail"]

    def test_audio_answer_rejects_when_model_disallows_audio(
        self, audio_api_client, isolated_db, monkeypatch
    ):
        """HTTP 400 when the configured catalog model does not accept audio."""
        interview_id = _seed_two_question_interview("audio-api-disabled")
        monkeypatch.setattr(
            "app.platform.services.config.ConfigService.get_config",
            lambda: AppConfig(
                provider_type="openai-compatible",
                base_url="http://localhost",
                model="text-only",
                llm_preset_id="text-only",
            ),
        )
        monkeypatch.setattr(
            "app.platform.services.llm_catalog.LLMCatalogService.get_model",
            lambda preset_id: LLMModelEntry(
                id=preset_id,
                display_name="Text only",
                provider_type="openai-compatible",
                model="text-only",
                base_url="http://localhost",
                api_key_required=False,
                accepts_audio_input=False,
            ),
        )
        wav_bytes = minimal_wav_bytes()

        response = audio_api_client.post(
            f"/interview/{interview_id}/audio-answer",
            data={"question_id": "q1"},
            files={"file": ("answer.wav", wav_bytes, "audio/wav")},
        )

        assert response.status_code == 400
        assert "audio input" in response.json()["detail"].lower()

    def test_audio_answer_rejects_when_whisper_unavailable(
        self, client, isolated_db, override_ws_ai_provider, monkeypatch
    ):
        """HTTP 503 when Whisper is not loaded on the application."""
        monkeypatch.setattr(
            "app.interview.services.answer_processing.AnswerProcessingService.require_audio_answer_enabled",
            staticmethod(lambda: None),
        )
        override_ws_ai_provider(client, [])
        interview_id = _seed_two_question_interview("audio-api-no-whisper")
        client.app.state.speech_transcriber = None
        wav_bytes = minimal_wav_bytes()

        with patch(
            "app.interview.api.routes.is_installed",
            return_value=False,
        ):
            response = client.post(
                f"/interview/{interview_id}/audio-answer",
                data={"question_id": "q1"},
                files={"file": ("answer.wav", wav_bytes, "audio/wav")},
            )

        assert response.status_code == 503
        assert "Speech model" in response.json()["detail"]


class TestInterviewAudioAnswerPage:
    """Tests for audio answer controls on the interview page."""

    def test_interview_page_shows_audio_controls_when_enabled(
        self, client, monkeypatch
    ):
        """Record / Send audio buttons render when LLM and Whisper are ready."""
        interview = _active_interview_read("audio-ui-1")
        monkeypatch.setattr(
            "app.interview.services.page.LLMCatalogService.get_model",
            lambda preset_id: LLMModelEntry(
                id=preset_id,
                display_name="Audio model",
                provider_type="openai-compatible",
                model="audio-model",
                base_url="http://localhost",
                api_key_required=False,
                accepts_audio_input=True,
            ),
        )
        page_context = InterviewPageService.build_page_context(
            interview,
            config=AppConfig(
                provider_type="openai-compatible",
                base_url="http://localhost",
                model="audio-model",
                llm_preset_id="audio-model",
            ),
            question_voice_enabled=False,
        )

        with (
            patch(
                "app.interview.api.routes.InterviewPageService.load_interview",
                return_value=interview,
            ),
            patch(
                "app.interview.api.routes.preload_whisper_for_active_interview",
                new=AsyncMock(),
            ),
            patch(
                "app.interview.api.routes.InterviewPageService.build_page_context",
                return_value=page_context,
            ),
            patch(
                "app.interview.api.routes.SpeechModelPageService.build_page_context",
                return_value=_speech_model_page_context(),
            ),
            patch(
                "app.interview.api.routes.QuestionVoicePageService.build_page_context",
                new=AsyncMock(return_value=_question_voice_page_context()),
            ),
        ):
            response = client.get("/interview/audio-ui-1")

        assert response.status_code == 200
        assert 'id="audio-record-btn"' in response.text
        assert 'data-audio-answer-enabled="true"' in response.text
        assert "interview_audio_answer.js" in response.text

    def test_interview_page_hides_audio_controls_without_catalog_flag(self, client):
        """Audio controls stay hidden when the configured model is text-only."""
        interview = _active_interview_read("audio-ui-2")
        page_context = InterviewPageService.build_page_context(
            interview,
            config=AppConfig(
                provider_type="openai-compatible",
                base_url="http://localhost",
                model="text-model",
                llm_preset_id="text-model",
            ),
            question_voice_enabled=False,
        )

        with (
            patch(
                "app.interview.api.routes.InterviewPageService.load_interview",
                return_value=interview,
            ),
            patch(
                "app.interview.api.routes.preload_whisper_for_active_interview",
                new=AsyncMock(),
            ),
            patch(
                "app.interview.api.routes.InterviewPageService.build_page_context",
                return_value=page_context,
            ),
            patch(
                "app.interview.api.routes.SpeechModelPageService.build_page_context",
                return_value=_speech_model_page_context(),
            ),
            patch(
                "app.interview.api.routes.QuestionVoicePageService.build_page_context",
                new=AsyncMock(return_value=_question_voice_page_context()),
            ),
        ):
            response = client.get("/interview/audio-ui-2")

        assert response.status_code == 200
        assert 'id="audio-record-btn"' not in response.text
        assert 'data-audio-answer-enabled="true"' not in response.text
