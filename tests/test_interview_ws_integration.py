# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket integration tests using real answer processing and fake AI."""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from app.shared.infrastructure.uow import UnitOfWork
from tests.fakes import answer_evaluation_json


@pytest.fixture
def client():
    """FastAPI test client without running init_db on startup."""
    with patch("app.main.init_db"):
        from app.main import create_app

        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


def _seed_interview(interview_id: str = "ws-int-1") -> str:
    """Create an active interview with one unanswered question.

    Args:
        interview_id: Interview primary key.

    Returns:
        The interview id.
    """
    with UnitOfWork(auto_commit=True) as uow:
        uow.interviews.add(
            Interview(
                id=interview_id,
                level="junior",
                language="python",
                locale="en",
                category="basics",
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
    client, isolated_db, patch_ai_provider
):
    """WS answer uses AnswerProcessingService; only the AI provider is faked."""
    interview_id = _seed_interview()
    patch_ai_provider([answer_evaluation_json(score=4, follow_up_needed=False)])

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

    assert feedback == {
        "type": "feedback",
        "question_id": "q1",
        "order": 1,
        "round": 0,
        "follow_up_question": None,
        "next_question": {
            "question_id": "q2",
            "order": 2,
            "question_text": "Question two?",
            "question_code": None,
        },
    }

    reloaded = InterviewQuery.get_interview(interview_id)
    assert reloaded is not None
    answer = next(a for a in reloaded.answers if a.question_id == "q1")
    assert answer.answer_text == "My structured answer."
    assert answer.score == 4
