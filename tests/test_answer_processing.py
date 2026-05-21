# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for answer processing with a deterministic fake AI provider."""

import json

import pytest

from app.interview.services.answer_processing import AnswerProcessingService
from app.interview.services.events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
)
from app.interview.services.query import InterviewQuery
from app.shared.domain.exceptions import InterviewNotActiveError
from app.shared.infrastructure.models import Answer, Interview
from app.shared.infrastructure.uow import UnitOfWork
from tests.fakes import answer_evaluation_json, follow_up_evaluation_json


def _seed_two_question_interview(interview_id: str = "ap-test-1") -> str:
    """Persist an active interview with two unanswered questions.

    Args:
        interview_id: Interview primary key.

    Returns:
        The interview id.
    """
    with UnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            level="junior",
            language="python",
            locale="en",
            category="basics",
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
    isolated_db, patch_ai_provider
):
    """Initial answer is scored and the client receives the next question."""
    interview_id = _seed_two_question_interview()
    patch_ai_provider([answer_evaluation_json(score=5, follow_up_needed=False)])

    events = await AnswerProcessingService.process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Lists are mutable.",
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
    }

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1" and a.round == 0)
    assert q1.answer_text == "Lists are mutable."
    assert q1.score == 5
    assert q1.feedback is not None
    assert len(reloaded.answers) == 2


@pytest.mark.asyncio
async def test_process_answer_creates_follow_up_round(isolated_db, patch_ai_provider):
    """When AI requests a follow-up, a new unanswered round row is created."""
    interview_id = _seed_two_question_interview("ap-test-2")
    patch_ai_provider(
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
    isolated_db, patch_ai_provider
):
    """Answering a follow-up round persists score and advances to the next question."""
    interview_id = "ap-test-3"
    with UnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            level="junior",
            language="python",
            locale="en",
            category="basics",
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

    patch_ai_provider(
        [follow_up_evaluation_json(score=4, needs_further_follow_up=False)]
    )

    events = await AnswerProcessingService.process_answer_submission(
        interview_id=interview_id,
        question_id="q1",
        answer_text="Follow-up answer text.",
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
async def test_process_answer_rejects_completed_interview(
    isolated_db, patch_ai_provider
):
    """Completed interviews cannot accept new answers."""
    interview_id = "ap-test-4"
    with UnitOfWork(auto_commit=True) as uow:
        interview = Interview(
            id=interview_id,
            level="junior",
            language="python",
            category="basics",
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

    patch_ai_provider([answer_evaluation_json()])

    with pytest.raises(InterviewNotActiveError):
        await AnswerProcessingService.process_answer_submission(
            interview_id=interview_id,
            question_id="q1",
            answer_text="Too late.",
        )
