# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for full theory flow: submit answers, next questions, finish, end interview."""

from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import answer_evaluation_json, follow_up_evaluation_json
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


class TestTheoryFullFlow:
    """End-to-end theory interaction via WebSocket."""

    def test_submit_all_questions_finish_section(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """Answer all theory questions + finish section moves to completed."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="theory-full-1",
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
            ),
            [
                Answer(
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q1?",
                ),
                Answer(
                    question_id="q2",
                    order=2,
                    round=0,
                    question_text="Q2?",
                ),
            ],
            question_count=2,
        )

        override_ws_ai_provider(
            client,
            [
                answer_evaluation_json(score=4, follow_up_needed=False),
                answer_evaluation_json(score=4, follow_up_needed=False),
            ],
        )

        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            # Answer Q1
            ws.send_json({
                "type": "answer",
                "question_id": "q1",
                "answer_text": "Answer one",
            })
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb1 = ws.receive_json()
            assert fb1["type"] == "feedback"
            assert fb1["question_id"] == "q1"

            # Next question shown
            assert fb1["next_question"]["question_id"] == "q2"

            # Answer Q2
            ws.send_json({
                "type": "answer",
                "question_id": "q2",
                "answer_text": "Answer two",
            })
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb2 = ws.receive_json()
            assert fb2["type"] == "feedback"
            assert fb2["question_id"] == "q2"
            assert fb2["next_question"] is None

            # Finish the section
            ws.send_json({"type": "complete"})
            assert ws.receive_json() == {"type": "evaluating"}
            complete = ws.receive_json()
            assert complete["type"] == "interview_completed"

        # Check DB state
        reloaded = InterviewQuery.load(interview_id)
        assert reloaded is not None
        assert reloaded.status == "completed"
        q1 = next(a for a in reloaded.answers if a.question_id == "q1")
        q2 = next(a for a in reloaded.answers if a.question_id == "q2")
        assert q1.answer_text == "Answer one"
        assert q1.score == 4
        assert q2.answer_text == "Answer two"
        assert q2.score == 4

    def test_follow_up_chain(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """Answer triggers follow-up; follow-up answer finishes round."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="theory-followup-1",
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
            ),
            [
                Answer(
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q1?",
                ),
                Answer(
                    question_id="q2",
                    order=2,
                    round=0,
                    question_text="Q2?",
                ),
            ],
            question_count=2,
        )

        # First evaluation: follow-up needed
        # Second evaluation: follow-up answer (no more follow-ups)
        override_ws_ai_provider(
            client,
            [
                answer_evaluation_json(
                    score=3,
                    follow_up_needed=True,
                    follow_up_question="Explain deeper.",
                ),
                follow_up_evaluation_json(
                    score=4,
                    needs_further_follow_up=False,
                ),
            ],
        )

        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            # Answer Q1 → triggers follow-up
            ws.send_json({
                "type": "answer",
                "question_id": "q1",
                "answer_text": "Hint of an answer",
            })
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb1 = ws.receive_json()
            assert fb1["type"] == "feedback"
            assert fb1["follow_up_question"] == "Explain deeper."

            # Answer follow-up
            ws.send_json({
                "type": "answer",
                "question_id": "q1",
                "answer_text": "Deeper explanation",
            })
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb2 = ws.receive_json()
            assert fb2["type"] == "feedback"
            assert fb2["follow_up_question"] is None
            assert fb2["next_question"]["question_id"] == "q2"

    def test_end_interview_mid_session(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """End interview sidebar button completes session early."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="theory-end-1",
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
            ),
            [
                Answer(
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q1?",
                ),
            ],
            question_count=1,
        )

        override_ws_ai_provider(client, [])

        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            ws.send_json({"type": "complete"})
            assert ws.receive_json() == {"type": "evaluating"}
            msg = ws.receive_json()
            assert msg["type"] == "interview_completed"

        reloaded = InterviewQuery.load(interview_id)
        assert reloaded is not None
        assert reloaded.status == "completed"
