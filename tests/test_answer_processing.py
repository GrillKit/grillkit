# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for answer processing with a deterministic fake AI provider."""

import asyncio
from datetime import UTC, datetime, timedelta
import json

import pytest

from app.interview.domain.entities import Answer as DomainAnswer
from app.interview.domain.exceptions import InterviewNotActiveError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.answer_ai_evaluation import AnswerAiEvaluationService
from app.interview.services.answer_processing import AnswerProcessingService
from app.interview.services.events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
)
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import answer_evaluation_json, follow_up_evaluation_json
from tests.helpers.selection import minimal_selection_spec


def _seed_two_question_interview(interview_id: str = "ap-test-1") -> str:
    """Persist an active interview with two unanswered questions.

    Args:
        interview_id: Interview primary key.

    Returns:
        The interview id.
    """
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
async def test_process_answer_persists_score_and_next_question(
    isolated_db, fake_ai_provider
):
    """Initial answer is scored and the client receives the next question."""
    interview_id = _seed_two_question_interview()
    provider = fake_ai_provider(
        [answer_evaluation_json(score=5, follow_up_needed=False)]
    )

    events = await AnswerProcessingService.process_answer_submission(
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
    assert feedback.next_question == {
        "question_id": "q2",
        "order": 2,
        "question_text": "Question two?",
        "question_code": None,
        "round": 0,
    }

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == "Lists are mutable."
    assert q1.score == 5
    assert q1.feedback is not None
    assert len(reloaded.answers) == 2


@pytest.mark.asyncio
async def test_process_answer_creates_follow_up_round(isolated_db, fake_ai_provider):
    """When AI requests a follow-up, a new unanswered round row is created."""
    interview_id = _seed_two_question_interview("ap-test-2")
    provider = fake_ai_provider(
        [
            answer_evaluation_json(
                score=3,
                follow_up_needed=True,
                follow_up_question="Explain big-O of append.",
            )
        ]
    )

    events = await AnswerProcessingService.process_answer_submission(
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

    reloaded = InterviewQuery.get_interview(interview_id)
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
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q1",
                order=1,
                round=1,
                question_text="Follow-up question?",
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
        [follow_up_evaluation_json(score=4, needs_further_follow_up=False)]
    )

    events = await AnswerProcessingService.process_answer_submission(
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

    reloaded = InterviewQuery.get_interview(interview_id)
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
        [follow_up_evaluation_json(score=4, needs_further_follow_up=False)]
    )

    events = await AnswerProcessingService.process_answer_submission(
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

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    last_follow_up = next(
        a for a in reloaded.answers if a.question_id == "q1" and a.round == 2
    )
    assert last_follow_up.answer_text == "Second follow-up answer."
    assert last_follow_up.score is None

    await asyncio.sleep(0.05)

    reloaded = InterviewQuery.get_interview(interview_id)
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
    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            selection_spec=minimal_selection_spec(categories=["basics"]),
            question_count=1,
            question_ids=json.dumps(["q1"]),
            status="completed",
        )
        uow.interviews.add(interview)
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q1",
                order=1,
                round=0,
                question_text="Done?",
            )
        )

    provider = fake_ai_provider([answer_evaluation_json()])

    with pytest.raises(InterviewNotActiveError):
        await AnswerProcessingService.process_answer_submission(
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
    with InterviewUnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            question_count=2,
            question_ids=json.dumps(["q1", "q2"]),
            question_time_limit_seconds=limit_seconds,
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
                started_at=started_at,
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
async def test_process_timeout_when_display_shows_zero(isolated_db):
    """WS timeout is accepted when UI remaining is 0 but deadline is sub-second away."""
    started = datetime.now(UTC) - timedelta(seconds=59, milliseconds=500)
    interview_id = _seed_timed_interview(started_at=started, limit_seconds=60)

    events = await AnswerProcessingService.process_timeout_submission(
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

    events = await AnswerProcessingService.process_timeout_submission(
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

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == DomainAnswer.TIME_EXPIRED_ANSWER_TEXT
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
        row = uow.answers.get_by_interview_question_round(interview_id, "q1", 0)
        uow.answers.set_answer_text(row, "Answer in progress.")

    events = await AnswerProcessingService.process_timeout_submission(
        interview_id=interview_id,
        question_id="q1",
        round_num=0,
    )

    assert events == []
    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == "Answer in progress."
    assert q1.score is None


@pytest.mark.asyncio
async def test_timeout_during_ai_evaluation_preserves_score(
    isolated_db, fake_ai_provider, monkeypatch
):
    """Timeout sent while AI runs does not block persisting the real score."""
    import asyncio

    started = datetime.now(UTC) - timedelta(seconds=30)
    interview_id = _seed_timed_interview(started_at=started)
    provider = fake_ai_provider(
        [answer_evaluation_json(score=5, follow_up_needed=False)]
    )

    orig_eval = AnswerAiEvaluationService.evaluate

    async def slow_eval(**kwargs):
        await asyncio.sleep(0.05)
        return await orig_eval(**kwargs)

    monkeypatch.setattr(AnswerAiEvaluationService, "evaluate", staticmethod(slow_eval))

    events: list = []
    gen = AnswerProcessingService.stream_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Valid on-time answer.",
        provider=provider,
    )
    async for event in gen:
        events.append(event)
        if type(event).__name__ == "EvaluatingEvent":
            timeout_events = await AnswerProcessingService.process_timeout_submission(
                interview_id=interview_id,
                question_id="q1",
                round_num=0,
            )
            assert timeout_events == []

    assert any(type(e).__name__ == "AnswerFeedbackEvent" for e in events)
    q1 = next(
        a
        for a in InterviewQuery.get_interview(interview_id).answers
        if a.question_id == "q1"
    )
    assert q1.answer_text == "Valid on-time answer."
    assert q1.score == 5


@pytest.mark.asyncio
async def test_late_answer_submission_treated_as_timeout(isolated_db, fake_ai_provider):
    """Submitting after the deadline skips AI and scores zero."""
    started = datetime.now(UTC) - timedelta(seconds=120)
    interview_id = _seed_timed_interview(started_at=started)
    provider = fake_ai_provider([answer_evaluation_json(score=5)])

    events = await AnswerProcessingService.process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Too late but trying anyway.",
        provider=provider,
    )

    assert len(events) == 1
    assert isinstance(events[0], AnswerFeedbackEvent)
    assert events[0].timed_out is True

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.score == 0
    assert q1.answer_text == DomainAnswer.TIME_EXPIRED_ANSWER_TEXT
