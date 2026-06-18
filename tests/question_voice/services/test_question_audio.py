# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for question-audio orchestration."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.platform.services.config import AppConfig
from app.question_voice.services.question_audio import _resolve_answer, get_question_audio_path
from app.question_voice.services.tts_exceptions import QuestionVoiceDisabledError


def _make_answer(
    *,
    answer_id: int = 1,
    question_text: str = "What is Python?",
    answer_text: str | None = None,
) -> AnswerRead:
    """Build an AnswerRead for tests."""
    return AnswerRead(
        id=answer_id,
        question_id="q1",
        order=1,
        round=0,
        question_text=question_text,
        question_code=None,
        answer_text=answer_text,
        score=None,
        feedback=None,
        started_at=None,
    )


def _make_interview(answers: list[AnswerRead]) -> InterviewRead:
    """Build an InterviewRead for tests."""
    return InterviewRead(
        id="test-interview-id",
        status="active",
        locale="en",
        selection_spec="{}",
        question_ids='["q1"]',
        question_count=len(answers),
        question_time_limit_seconds=None,
        answers=answers,
        score=None,
        overall_feedback=None,
        started_at=datetime.now(),
        completed_at=None,
    )


class TestGetQuestionAudioPath:
    """Tests for get_question_audio_path."""

    @pytest.mark.asyncio
    async def test_raises_when_no_config(self):
        """Missing config raises QuestionVoiceDisabledError."""
        with patch(
            "app.question_voice.services.question_audio.ConfigService.get_config",
            return_value=None,
        ):
            with pytest.raises(QuestionVoiceDisabledError):
                await get_question_audio_path("interview-id")

    @pytest.mark.asyncio
    async def test_raises_when_voice_disabled(self):
        """Disabled voice in config raises QuestionVoiceDisabledError."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
        )
        with patch(
            "app.question_voice.services.question_audio.ConfigService.get_config",
            return_value=config,
        ):
            with pytest.raises(QuestionVoiceDisabledError):
                await get_question_audio_path("interview-id")

    @pytest.mark.asyncio
    async def test_returns_cached_path_with_answer_id(self):
        """Enabled voice returns WAV path for a specific answer_id."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )
        answer = _make_answer(answer_id=7)
        interview = _make_interview([answer])
        cached_path = Path("/tmp/cache/question.wav")

        with (
            patch(
                "app.question_voice.services.question_audio.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.question_voice.services.question_audio.InterviewQuery.get_active_interview_or_raise",
                return_value=interview,
            ),
            patch(
                "app.question_voice.services.question_audio.TtsCacheService.get_or_fetch",
                new_callable=AsyncMock,
                return_value=cached_path,
            ) as mock_cache,
        ):
            result = await get_question_audio_path("interview-id", answer_id=7)

        assert result == cached_path
        mock_cache.assert_called_once_with(
            "en_US-lessac-medium",
            "en",
            "What is Python?",
        )

    @pytest.mark.asyncio
    async def test_returns_cached_path_for_current_question(self):
        """Enabled voice returns path for current unanswered question."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )
        answer = _make_answer(answer_id=3)
        interview = _make_interview([answer])
        cached_path = Path("/tmp/cache/current.wav")

        with (
            patch(
                "app.question_voice.services.question_audio.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.question_voice.services.question_audio.InterviewQuery.get_active_interview_or_raise",
                return_value=interview,
            ),
            patch(
                "app.question_voice.services.question_audio.TtsCacheService.get_or_fetch",
                new_callable=AsyncMock,
                return_value=cached_path,
            ) as mock_cache,
        ):
            result = await get_question_audio_path("interview-id")

        assert result == cached_path
        mock_cache.assert_called_once_with(
            "en_US-lessac-medium",
            "en",
            "What is Python?",
        )


class TestResolveAnswer:
    """Tests for _resolve_answer helper."""

    def test_returns_matching_answer_by_id(self):
        """answer_id selects the matching answer."""
        target = _make_answer(answer_id=2, question_text="Second question")
        interview = _make_interview([_make_answer(answer_id=1), target])
        result = _resolve_answer(interview, answer_id=2)
        assert result.id == 2
        assert result.question_text == "Second question"

    def test_raises_when_answer_not_found(self):
        """Unknown answer_id raises ValueError."""
        interview = _make_interview([_make_answer(answer_id=1)])
        with pytest.raises(ValueError, match="Answer not found"):
            _resolve_answer(interview, answer_id=99)

    def test_raises_when_answer_already_submitted(self):
        """Already answered answer raises ValueError."""
        answered = _make_answer(answer_id=1, answer_text="Already answered")
        interview = _make_interview([answered])
        with pytest.raises(ValueError, match="already submitted"):
            _resolve_answer(interview, answer_id=1)

    def test_raises_when_question_text_empty(self):
        """Empty question text raises ValueError."""
        empty = _make_answer(answer_id=1, question_text="  ")
        interview = _make_interview([empty])
        with pytest.raises(ValueError, match="Question text is empty"):
            _resolve_answer(interview, answer_id=1)

    def test_returns_current_unanswered_when_no_answer_id(self):
        """No answer_id picks the first unanswered question."""
        unanswered = _make_answer(answer_id=5)
        interview = _make_interview([unanswered])
        result = _resolve_answer(interview, answer_id=None)
        assert result.id == 5

    def test_raises_when_no_unanswered_question(self):
        """All answered raises ValueError."""
        answered = _make_answer(answer_id=1, answer_text="Done")
        interview = _make_interview([answered])
        with pytest.raises(ValueError, match="No unanswered question"):
            _resolve_answer(interview, answer_id=None)

    def test_raises_when_current_question_text_empty(self):
        """Empty current question text raises ValueError."""
        empty = _make_answer(answer_id=1, question_text="")
        interview = _make_interview([empty])
        with pytest.raises(ValueError, match="Question text is empty"):
            _resolve_answer(interview, answer_id=None)
