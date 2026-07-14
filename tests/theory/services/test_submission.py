# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheorySubmissionService text and audio answer flows."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.audio_probe import minimal_wav_bytes
from app.interview.domain.exceptions import InterviewNotActiveError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
    TranscriptEvent,
)
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from app.theory.domain.entities import TheoryTask
from app.theory.services.evaluator.service import TheoryEvaluatorService
from app.theory.services.submission import TheorySubmissionService
from tests.fakes import answer_evaluation_json, follow_up_evaluation_json
from tests.helpers.interview_seed import (
    persist_interview_with_answers,
    seed_two_question_interview,
)
from tests.helpers.selection import minimal_selection_spec
from tests.helpers.transcription import FakeTranscriber


async def _process_answer_submission(**kwargs):
    """Run text answer submission inside an auto-commit UoW."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = TheorySubmissionService(uow)
        return await service.process_answer_submission(**kwargs)


async def _process_timeout_submission(**kwargs):
    """Run timeout submission inside an auto-commit UoW."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = TheorySubmissionService(uow)
        return await service.process_timeout_submission(**kwargs)


async def _process_audio_answer_submission(**kwargs):
    """Run audio answer submission inside an auto-commit UoW."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = TheorySubmissionService(uow)
        return await service.process_audio_answer_submission(**kwargs)


@pytest.mark.asyncio
async def test_process_answer_persists_score_and_next_question(
    isolated_db, fake_ai_provider
):
    """Initial answer is scored and the client receives the next question."""
    interview_id = seed_two_question_interview()
    provider = fake_ai_provider(
        [answer_evaluation_json(score=5, follow_up_needed=False)]
    )

    events = await _process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Lists are mutable.",
        provider=provider,
    )

    assert [type(e) for e in events] == [
        AnswerSavedEvent,
        EvaluatingEvent,
        AnswerFeedbackEvent,
    ]
    feedback = events[2]
    assert isinstance(feedback, AnswerFeedbackEvent)
    assert feedback.follow_up_needed is False
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    q2 = next(a for a in reloaded.answers if a.question_id == "q2" and a.round == 0)
    assert feedback.next_question == {
        "id": q2.id,
        "question_id": "q2",
        "order": 2,
        "question_text": "Question two?",
        "question_code": None,
        "round": 0,
    }

    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == "Lists are mutable."
    assert q1.score == 5
    assert q1.feedback is not None
    assert len(reloaded.answers) == 2


@pytest.mark.asyncio
async def test_process_answer_creates_follow_up_round(isolated_db, fake_ai_provider):
    """When AI requests a follow-up, a new unanswered round row is created."""
    interview_id = seed_two_question_interview("ap-test-2")
    provider = fake_ai_provider(
        [
            answer_evaluation_json(
                score=3,
                follow_up_needed=True,
                follow_up_question="Explain big-O of append.",
            )
        ]
    )

    events = await _process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Partial answer.",
        provider=provider,
    )

    feedback = events[2]
    assert isinstance(feedback, AnswerFeedbackEvent)
    assert feedback.follow_up_needed is True
    assert feedback.follow_up_text == "Explain big-O of append."
    assert feedback.next_question is None

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    rounds = [a for a in reloaded.answers if a.question_id == "q1"]
    assert len(rounds) == 2
    follow_up = next(a for a in rounds if a.round == 1)
    assert follow_up.question_text == "Explain big-O of append."
    assert follow_up.answer_text is None


@pytest.mark.asyncio
async def test_process_follow_up_answer_without_another_follow_up(
    isolated_db, fake_ai_provider
):
    """Answering a follow-up round persists score and advances to the next question."""
    interview_id = "ap-test-3"
    initial = Answer(
        question_id="q1",
        order=1,
        round=0,
        question_text="Original question?",
    )
    initial.answer_text = "First answer"
    initial.score = 3
    initial.feedback = "OK"
    first_follow_up = Answer(
        question_id="q1",
        order=1,
        round=1,
        question_text="Follow-up question?",
    )
    persist_interview_with_answers(
        Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            initial,
            first_follow_up,
            Answer(
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            ),
        ],
        question_count=2,
    )

    provider = fake_ai_provider(
        [follow_up_evaluation_json(score=4, needs_further_follow_up=False)]
    )

    events = await _process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Follow-up answer text.",
        provider=provider,
    )

    feedback = events[2]
    assert isinstance(feedback, AnswerFeedbackEvent)
    assert feedback.round == 1
    assert feedback.follow_up_needed is False
    assert feedback.next_question is not None
    assert feedback.next_question["question_id"] == "q2"

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 1
    )
    assert follow_up.answer_text == "Follow-up answer text."
    assert follow_up.score == 4


@pytest.mark.asyncio
async def test_last_follow_up_advances_immediately_and_evaluates_in_background(
    isolated_db, fake_ai_provider
):
    """The last follow-up round advances without waiting for AI evaluation."""
    interview_id = "ap-test-last-follow-up"
    initial = Answer(
        question_id="q1",
        order=1,
        round=0,
        question_text="Original question?",
    )
    initial.answer_text = "First answer"
    initial.score = 3
    initial.feedback = "OK"
    first_follow_up = Answer(
        question_id="q1",
        order=1,
        round=1,
        question_text="First follow-up?",
    )
    first_follow_up.answer_text = "First follow-up answer"
    first_follow_up.score = 3
    first_follow_up.feedback = "OK"
    persist_interview_with_answers(
        Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            initial,
            first_follow_up,
            Answer(
                question_id="q1",
                order=1,
                round=2,
                question_text="Second follow-up?",
            ),
            Answer(
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            ),
        ],
        question_count=2,
    )

    provider = fake_ai_provider(
        [follow_up_evaluation_json(score=4, needs_further_follow_up=False)]
    )

    events = await _process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Second follow-up answer.",
        provider=provider,
    )

    assert len(events) == 2
    assert isinstance(events[0], AnswerSavedEvent)
    feedback = events[1]
    assert isinstance(feedback, AnswerFeedbackEvent)
    assert not any(isinstance(event, EvaluatingEvent) for event in events)
    assert feedback.round == 2
    assert feedback.next_question is not None
    assert feedback.next_question["question_id"] == "q2"

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.answer_text == "Second follow-up answer."
    assert last_follow_up.score is None

    await asyncio.sleep(0.05)

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.score == 4
    assert last_follow_up.feedback is not None


@pytest.mark.asyncio
async def test_process_answer_rejects_completed_interview(
    isolated_db, fake_ai_provider
):
    """Completed interviews cannot accept new answers."""
    interview_id = "ap-test-4"
    persist_interview_with_answers(
        Interview(
            id=interview_id,
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="completed",
        ),
        [
            Answer(
                question_id="q1",
                order=1,
                round=0,
                question_text="Done?",
            )
        ],
        question_count=1,
    )

    provider = fake_ai_provider([answer_evaluation_json()])

    with pytest.raises(InterviewNotActiveError):
        await _process_answer_submission(
            interview_id=interview_id,
            question_id="q1",
            answer_text="Too late.",
            provider=provider,
        )


def _seed_timed_interview(
    interview_id: str = "ap-timer-default",
    *,
    started_at: datetime,
    limit_seconds: int = 60,
) -> str:
    """Persist an active interview with an expired timer on question one.

    Args:
        interview_id: Interview primary key.
        started_at: When the current round timer started.
        limit_seconds: Per-round limit in seconds.

    Returns:
        The interview id.
    """
    return persist_interview_with_answers(
        Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            Answer(
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
                started_at=started_at,
            ),
            Answer(
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            ),
        ],
        question_count=2,
        task_time_limit_seconds=limit_seconds,
    )


@pytest.mark.asyncio
async def test_process_timeout_when_display_shows_zero(isolated_db):
    """WS timeout is accepted when UI remaining is 0 but deadline is sub-second away."""
    started = datetime.now(UTC) - timedelta(seconds=59, milliseconds=500)
    interview_id = _seed_timed_interview(started_at=started, limit_seconds=60)

    events = await _process_timeout_submission(
        interview_id=interview_id,
        question_id="q1",
        round_num=0,
    )

    assert len(events) == 1
    assert events[0].timed_out is True


@pytest.mark.asyncio
async def test_process_timeout_scores_zero_and_advances(isolated_db):
    """Expired round is recorded with zero score without calling AI."""
    started = datetime.now(UTC) - timedelta(seconds=120)
    interview_id = _seed_timed_interview(started_at=started)

    events = await _process_timeout_submission(
        interview_id=interview_id,
        question_id="q1",
        round_num=0,
    )

    assert len(events) == 1
    feedback = events[0]
    assert isinstance(feedback, AnswerFeedbackEvent)
    assert feedback.timed_out is True
    assert feedback.next_question is not None
    assert feedback.next_question["question_id"] == "q2"

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == TheoryTask.TIME_EXPIRED_ANSWER_TEXT
    assert q1.score == 0
    q2 = next(a for a in reloaded.answers if a.question_id == "q2")
    assert q2.started_at is not None


@pytest.mark.asyncio
async def test_timeout_ignored_while_answer_pending_evaluation(
    isolated_db,
):
    """Timeout during AI evaluation must not overwrite a submitted answer."""
    started = datetime.now(UTC) - timedelta(seconds=30)
    interview_id = _seed_timed_interview(started_at=started)
    with InterviewUnitOfWork(auto_commit=True) as uow:
        section = uow.theory_sections.get_aggregate(interview_id)
        assert section is not None
        current = section.find_task("q1", 0)
        updated = section.with_task_text(current.id, "Answer in progress.")
        uow.theory_sections.save_aggregate(updated)

    events = await _process_timeout_submission(
        interview_id=interview_id,
        question_id="q1",
        round_num=0,
    )

    assert events == []
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == "Answer in progress."
    assert q1.score is None


@pytest.mark.asyncio
async def test_timeout_during_ai_evaluation_preserves_score(
    isolated_db, fake_ai_provider, monkeypatch
):
    """Timeout sent while AI runs does not block persisting the real score."""
    started = datetime.now(UTC) - timedelta(seconds=30)
    interview_id = _seed_timed_interview(started_at=started)
    provider = fake_ai_provider(
        [answer_evaluation_json(score=5, follow_up_needed=False)]
    )

    orig_eval = TheoryEvaluatorService.evaluate_submission

    async def slow_eval(**kwargs):
        await asyncio.sleep(0.05)
        return await orig_eval(**kwargs)

    monkeypatch.setattr(
        TheoryEvaluatorService,
        "evaluate_submission",
        staticmethod(slow_eval),
    )

    events: list = []
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = TheorySubmissionService(uow)
        gen = service.stream_answer_submission(
            interview_id=interview_id,
            question_id="q1",
            answer_text="Valid on-time answer.",
            provider=provider,
        )
        async for event in gen:
            events.append(event)
            if type(event).__name__ == "EvaluatingEvent":
                timeout_events = await _process_timeout_submission(
                    interview_id=interview_id,
                    question_id="q1",
                    round_num=0,
                )
                assert timeout_events == []

    assert any(type(e).__name__ == "AnswerFeedbackEvent" for e in events)
    q1 = next(
        a for a in InterviewQuery.load(interview_id).answers if a.question_id == "q1"
    )
    assert q1.answer_text == "Valid on-time answer."
    assert q1.score == 5


@pytest.mark.asyncio
async def test_late_answer_submission_treated_as_timeout(isolated_db, fake_ai_provider):
    """Submitting after the deadline skips AI and scores zero."""
    started = datetime.now(UTC) - timedelta(seconds=120)
    interview_id = _seed_timed_interview(started_at=started)
    provider = fake_ai_provider([answer_evaluation_json(score=5)])

    events = await _process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Too late but trying anyway.",
        provider=provider,
    )

    assert len(events) == 1
    assert isinstance(events[0], AnswerFeedbackEvent)
    assert events[0].timed_out is True

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.score == 0
    assert q1.answer_text == TheoryTask.TIME_EXPIRED_ANSWER_TEXT


@pytest.mark.asyncio
async def test_process_audio_answer_runs_transcription_and_evaluation(
    isolated_db, fake_ai_provider, monkeypatch
):
    """Audio answers yield saved, evaluating, transcript, and feedback events."""
    monkeypatch.setattr(
        TheorySubmissionService,
        "require_audio_answer_enabled",
        staticmethod(lambda: None),
    )
    interview_id = seed_two_question_interview("audio-ap-1")
    provider = fake_ai_provider(
        [answer_evaluation_json(score=5, follow_up_needed=False)]
    )
    transcriber = FakeTranscriber("spoken answer text")
    wav_bytes = minimal_wav_bytes(duration_sec=0.2)

    events = await _process_audio_answer_submission(
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

    reloaded = InterviewQuery.load(interview_id)
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
        TheorySubmissionService,
        "require_audio_answer_enabled",
        staticmethod(lambda: None),
    )
    interview_id = seed_two_question_interview("audio-ap-1")
    provider = fake_ai_provider([answer_evaluation_json()])
    transcriber = FakeTranscriber()

    with pytest.raises(ValueError, match="valid WAV"):
        await _process_audio_answer_submission(
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
        TheorySubmissionService,
        "require_audio_answer_enabled",
        staticmethod(lambda: None),
    )
    interview_id = "audio-ap-last-follow-up"
    initial = Answer(
        question_id="q1",
        order=1,
        round=0,
        question_text="Original question?",
    )
    initial.answer_text = "First answer"
    initial.score = 3
    initial.feedback = "OK"
    first_follow_up = Answer(
        question_id="q1",
        order=1,
        round=1,
        question_text="First follow-up?",
    )
    first_follow_up.answer_text = "First follow-up answer"
    first_follow_up.score = 3
    first_follow_up.feedback = "OK"
    persist_interview_with_answers(
        Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            initial,
            first_follow_up,
            Answer(
                question_id="q1",
                order=1,
                round=2,
                question_text="Second follow-up?",
            ),
            Answer(
                question_id="q2",
                order=2,
                round=0,
                question_text="Question two?",
            ),
        ],
        question_count=2,
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

    orig_eval = TheoryEvaluatorService.evaluate_submission

    async def slow_audio_eval(**kwargs):
        await asyncio.sleep(0.05)
        return await orig_eval(**kwargs)

    monkeypatch.setattr(
        TheoryEvaluatorService,
        "evaluate_submission",
        staticmethod(slow_audio_eval),
    )

    events = await _process_audio_answer_submission(
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

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.answer_text == "second follow-up spoken"
    assert last_follow_up.score is None

    await asyncio.sleep(0.05)

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.score == 4
