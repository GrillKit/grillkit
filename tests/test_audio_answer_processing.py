# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for audio answer submission orchestration."""

import asyncio
import json

import numpy as np
import pytest

from app.ai.audio_probe import minimal_wav_bytes
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.answer_ai_evaluation import AnswerAiEvaluationService
from app.interview.services.answer_processing import AnswerProcessingService
from app.interview.services.events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
    TranscriptEvent,
)
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import answer_evaluation_json, follow_up_evaluation_json
from tests.helpers.selection import minimal_selection_spec


class FakeTranscriber:
    """Deterministic speech transcriber for tests."""

    def __init__(self, text: str = "spoken answer text") -> None:
        """Initialize with a fixed transcript.

        Args:
            text: Text returned from ``transcribe``.
        """
        self.text = text
        self.last_audio: np.ndarray | None = None

    async def transcribe(self, audio: np.ndarray, locale: str) -> str:
        """Store audio samples and return the configured transcript.

        Args:
            audio: Mono float32 samples.
            locale: Interview locale (ignored).

        Returns:
            Configured transcript text.
        """
        del locale
        self.last_audio = audio
        return self.text


def _seed_two_question_interview(interview_id: str = "audio-ap-1") -> str:
    """Persist an active interview with two unanswered questions."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            question_count=2,
            question_ids=json.dumps(["q1", "q2"]),
            status="active",
        )
        uow.interviews.add(interview)
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
            )
        )
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            )
        )
    return interview_id


@pytest.mark.asyncio
async def test_process_audio_answer_runs_transcription_and_evaluation(
    isolated_db, fake_ai_provider, monkeypatch
):
    """Audio answers yield saved, evaluating, transcript, and feedback events."""
    monkeypatch.setattr(
        AnswerProcessingService,
        "require_audio_answer_enabled",
        staticmethod(lambda: None),
    )
    interview_id = _seed_two_question_interview()
    provider = fake_ai_provider(
        [answer_evaluation_json(score=5, follow_up_needed=False)]
    )
    transcriber = FakeTranscriber("spoken answer text")
    wav_bytes = minimal_wav_bytes(duration_sec=0.2)

    events = await AnswerProcessingService.process_audio_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        wav_bytes=wav_bytes,
        provider=provider,
        transcriber=transcriber,
    )

    assert [type(event) for event in events] == [
        AnswerSavedEvent,
        EvaluatingEvent,
        TranscriptEvent,
        AnswerFeedbackEvent,
    ]
    transcript = events[2]
    assert isinstance(transcript, TranscriptEvent)
    assert transcript.text == "spoken answer text"
    assert transcriber.last_audio is not None

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    answer = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert answer.answer_text == "spoken answer text"
    assert answer.score == 5


@pytest.mark.asyncio
async def test_process_audio_answer_rejects_invalid_wav(
    isolated_db, fake_ai_provider, monkeypatch
):
    """Invalid WAV payloads fail before any events are emitted."""
    monkeypatch.setattr(
        AnswerProcessingService,
        "require_audio_answer_enabled",
        staticmethod(lambda: None),
    )
    interview_id = _seed_two_question_interview()
    provider = fake_ai_provider([answer_evaluation_json()])
    transcriber = FakeTranscriber()

    with pytest.raises(ValueError, match="valid WAV"):
        await AnswerProcessingService.process_audio_answer_submission(
            interview_id=interview_id,
            question_id="q1",
            wav_bytes=b"not-wav",
            provider=provider,
            transcriber=transcriber,
        )


@pytest.mark.asyncio
async def test_process_audio_answer_last_follow_up_fast_path(
    isolated_db, fake_ai_provider, monkeypatch
):
    """Last follow-up round advances immediately and transcribes in-band."""
    monkeypatch.setattr(
        AnswerProcessingService,
        "require_audio_answer_enabled",
        staticmethod(lambda: None),
    )
    interview_id = "audio-ap-last-follow-up"
    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            question_count=2,
            question_ids=json.dumps(["q1", "q2"]),
            status="active",
        )
        uow.interviews.add(interview)
        initial = Answer(
            interview_id=interview_id,
            question_id="q1",
            order=1,
            round=0,
            question_text="Original question?",
        )
        initial.answer_text = "First answer"
        initial.score = 3
        initial.feedback = "OK"
        uow.answers.add(initial)
        first_follow_up = Answer(
            interview_id=interview_id,
            question_id="q1",
            order=1,
            round=1,
            question_text="First follow-up?",
        )
        first_follow_up.answer_text = "First follow-up answer"
        first_follow_up.score = 3
        first_follow_up.feedback = "OK"
        uow.answers.add(first_follow_up)
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q1",
                order=1,
                round=2,
                question_text="Second follow-up?",
            )
        )
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            )
        )

    provider = fake_ai_provider(
        [
            follow_up_evaluation_json(
                score=4,
                needs_further_follow_up=False,
            )
        ]
    )
    transcriber = FakeTranscriber("second follow-up spoken")
    wav_bytes = minimal_wav_bytes()

    orig_eval = AnswerAiEvaluationService.evaluate_with_audio

    async def slow_audio_eval(**kwargs):
        await asyncio.sleep(0.05)
        return await orig_eval(**kwargs)

    monkeypatch.setattr(
        AnswerAiEvaluationService,
        "evaluate_with_audio",
        staticmethod(slow_audio_eval),
    )

    events = await AnswerProcessingService.process_audio_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        wav_bytes=wav_bytes,
        provider=provider,
        transcriber=transcriber,
    )

    assert len(events) == 3
    assert isinstance(events[0], AnswerSavedEvent)
    assert isinstance(events[1], AnswerFeedbackEvent)
    assert isinstance(events[2], TranscriptEvent)
    assert not any(isinstance(event, EvaluatingEvent) for event in events)

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.answer_text == "second follow-up spoken"
    assert last_follow_up.score is None

    await asyncio.sleep(0.05)

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.score == 4
