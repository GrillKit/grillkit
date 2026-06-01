# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket integration tests using real answer processing and fake AI."""

from datetime import UTC, datetime, timedelta
import json

from app.ai.base import GenerationResult, Message
from app.interview.api.deps import get_ai_provider
from app.interview.domain.entities import Answer as DomainAnswer
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import FakeProvider, answer_evaluation_json
from tests.helpers.selection import minimal_selection_spec


class _FailingProvider(FakeProvider):
    """Fake provider that always raises like an OpenAI-compatible client."""

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Raise a provider error."""
        del messages, temperature, max_tokens
        raise ValueError(
            "API error: Error code: 404 - "
            "{'error': {'message': \"model 'qwen2.5-coder:7b-instruct-q4_K_M' not found\"}}"
        )


def _seed_interview(interview_id: str = "ws-int-1") -> str:
    """Create an active interview with one unanswered question.

    Args:
        interview_id: Interview primary key.

    Returns:
        The interview id.
    """
    with InterviewUnitOfWork(auto_commit=True) as uow:
        uow.interviews.add(
            Interview(
                id=interview_id,
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                question_count=2,
                question_ids=json.dumps(["q1", "q2"]),
                status="active",
            )
        )
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


def test_websocket_answer_runs_full_processing_pipeline(
    client, isolated_db, override_ws_ai_provider
):
    """WS answer uses AnswerProcessingService; only the AI provider is faked."""
    interview_id = _seed_interview()
    override_ws_ai_provider(
        client, [answer_evaluation_json(score=4, follow_up_needed=False)]
    )

    with client.websocket_connect(f"/interview/{interview_id}/ws") as ws:
        ws.send_json(
            {
                "type": "answer",
                "question_id": "q1",
                "answer_text": "My structured answer.",
            }
        )
        assert ws.receive_json() == {"type": "saved"}
        assert ws.receive_json() == {"type": "evaluating"}
        feedback = ws.receive_json()

    assert feedback["type"] == "feedback"
    assert feedback["question_id"] == "q1"
    assert feedback["round"] == 0
    assert feedback["timed_out"] is False
    assert feedback["follow_up_question"] is None
    assert feedback["next_question"] == {
        "question_id": "q2",
        "order": 2,
        "question_text": "Question two?",
        "question_code": None,
        "round": 0,
    }

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    answer = next(a for a in reloaded.answers if a.question_id == "q1")
    assert answer.answer_text == "My structured answer."
    assert answer.score == 4


def test_websocket_answer_ai_failure_returns_error(client, isolated_db):
    """WS answer surfaces AI failures instead of hanging on the evaluating state."""
    interview_id = _seed_interview("ws-ai-fail-1")
    provider = _FailingProvider([])

    async def _dep():
        yield provider

    client.app.dependency_overrides[get_ai_provider] = _dep
    try:
        with client.websocket_connect(f"/interview/{interview_id}/ws") as ws:
            ws.send_json(
                {
                    "type": "answer",
                    "question_id": "q1",
                    "answer_text": "My answer.",
                }
            )
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            err = ws.receive_json()
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)

    assert err["type"] == "error"
    assert "/config" in err["message"].lower()


def test_websocket_timeout_scores_zero(client, isolated_db, override_ws_ai_provider):
    """WS timeout records zero score and advances without AI."""
    interview_id = "ws-timeout-1"
    started = datetime.now(UTC) - timedelta(seconds=120)
    with InterviewUnitOfWork(auto_commit=True) as uow:
        uow.interviews.add(
            Interview(
                id=interview_id,
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                question_count=2,
                question_ids=json.dumps(["q1", "q2"]),
                question_time_limit_seconds=60,
                status="active",
            )
        )
        uow.answers.add(
            Answer(
                interview_id=interview_id,
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
                started_at=started,
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

    override_ws_ai_provider(client, [])

    with client.websocket_connect(f"/interview/{interview_id}/ws") as ws:
        ws.send_json({"type": "timeout", "question_id": "q1", "round": 0})
        feedback = ws.receive_json()

    assert feedback["type"] == "feedback"
    assert feedback["timed_out"] is True
    assert feedback["next_question"]["question_id"] == "q2"

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1")
    assert q1.answer_text == DomainAnswer.TIME_EXPIRED_ANSWER_TEXT
    assert q1.score == 0
