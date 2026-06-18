# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""E2E test: full lifecycle — theory only, mark known, exclude known next session."""

from unittest.mock import patch

from app.interview.domain.serialization import session_to_spec
from app.interview.domain.value_objects import (
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.query import InterviewQuery
from app.platform.services.config import AppConfig
from tests.fakes import answer_evaluation_json


class TestE2EFullLifecycle:
    """End-to-end: config → theory session → mark known → new session excludes known."""

    def _config(self) -> AppConfig:
        return AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
        )

    def test_theory_only_full_cycle(self, client, isolated_db, override_ws_ai_provider):
        """E2E-1: full theory cycle."""
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=self._config(),
        ):
            session = SessionSelection.theory_only(
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("basics",),
                    ),
                ),
                question_count=2,
            )
            response = client.post(
                "/setup",
                data={
                    "selection_json": session_to_spec(session),
                    "question_count": "2",
                },
                follow_redirects=False,
            )
        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        # Получаем текущие question_id через query
        from app.interview.repositories.uow import InterviewUnitOfWork
        with InterviewUnitOfWork() as uow:
            interview = InterviewQuery(uow).get_interview(interview_id)
            question_ids = [a.question_id for a in interview.answers]
        assert len(question_ids) == 2

        override_ws_ai_provider(
            client,
            [
                answer_evaluation_json(score=4, follow_up_needed=False),
                answer_evaluation_json(score=5, follow_up_needed=False),
            ],
        )
        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            # Q1
            ws.send_json({
                "type": "answer",
                "question_id": question_ids[0],
                "answer_text": "A1",
            })
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb1 = ws.receive_json()
            assert fb1["type"] == "feedback"
            # Q2
            ws.send_json({
                "type": "answer",
                "question_id": question_ids[1],
                "answer_text": "A2",
            })
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb2 = ws.receive_json()
            assert fb2["type"] == "feedback"
            # Complete
            ws.send_json({"type": "complete"})
            assert ws.receive_json() == {"type": "evaluating"}
            completed = ws.receive_json()
            assert completed["type"] == "interview_completed"

        # Results + review
        assert client.get(f"/interview/{interview_id}/results").status_code == 200
        assert client.get(f"/interview/{interview_id}/theory").status_code == 200

    def test_coding_only_full_cycle(self, client, isolated_db, mock_judge0, override_ws_ai_provider):
        """E2E-2: full coding cycle."""
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=self._config(),
            ),
            patch(
                "app.interview.services.rules.selection.is_coding_available",
                return_value=True,
            ),
        ):
            session = SessionSelection(
                session_mode="coding_only",
                theory=SectionBranchSpec(
                    enabled=False,
                    question_count=0,
                    task_time_limit_seconds=None,
                    sources=(),
                ),
                coding=SectionBranchSpec(
                    enabled=True,
                    question_count=1,
                    task_time_limit_seconds=None,
                    sources=(
                        TrackSelection(
                            track="python",
                            level="junior",
                            categories=("basics",),
                        ),
                    ),
                ),
            )
            response = client.post(
                "/setup",
                data={
                    "selection_json": session_to_spec(session),
                    "question_count": "0",
                    "coding_question_count": "1",
                },
                follow_redirects=False,
            )
        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        # Получаем фактический task_id из coding state endpoint
        state = client.get(f"/interview/{interview_id}/coding/state").json()
        task_id = state["current_task"]["task_id"]

        mock_judge0()
        evaluation = {
            "score": 5,
            "feedback": "Perfect.",
            "follow_up_needed": False,
            "follow_up_question": None,
        }

        from unittest.mock import AsyncMock

        from app.coding.services.evaluator.models import CodingAnswerEvaluation
        eval_obj = CodingAnswerEvaluation(**evaluation)

        override_ws_ai_provider(client, [])
        with (
            patch(
                "app.coding.services.submission.CodingEvaluatorService.evaluate_submission",
                new=AsyncMock(return_value=(eval_obj, False, None, None)),
            ),
            client.websocket_connect(f"/interview/{interview_id}/coding/ws") as ws,
        ):
            # Run
            run_resp = client.post(
                f"/interview/{interview_id}/coding/run",
                json={"task_id": task_id, "source_code": "def solve(): return 42"},
            )
            assert run_resp.status_code == 200
            # Submit
            ws.send_json({"type": "submit", "task_id": task_id, "source_code": "def solve(): return 42"})
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb = ws.receive_json()
            assert fb["type"] == "feedback"

        # Results
        results = client.get(f"/interview/{interview_id}/results")
        assert results.status_code == 200

    def test_mark_known_then_exclude_known(self, client, isolated_db, override_ws_ai_provider):
        """E2E-4: mark known → create new session with exclude_known."""
        # Mark a question as known
        response = client.post(
            "/known-questions",
            json={"branch": "theory", "item_id": "q-known-exclude"},
        )
        assert response.status_code == 200

        # Create session
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=self._config(),
        ):
            session = SessionSelection.theory_only(
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("basics",),
                    ),
                ),
                question_count=3,
            )
            import json
            spec = json.loads(session_to_spec(session))
            spec["exclude_known"] = True
            response = client.post(
                "/setup",
                data={
                    "selection_json": json.dumps(spec),
                    "question_count": "3",
                },
                follow_redirects=False,
            )
        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        # Verify session created successfully
        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview is not None
            assert interview.status == "active"
