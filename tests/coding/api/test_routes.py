# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding HTTP and WebSocket routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.coding.domain.value_objects import CodingRunResult
from app.coding.services.evaluator.models import CodingAnswerEvaluation
from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import CodingTask
from tests.helpers.coding_seed import seed_active_coding_interview


def _success_run_result() -> CodingRunResult:
    return CodingRunResult(
        status="success",
        stdout=None,
        stderr=None,
        compile_output=None,
        tests_passed=0,
        tests_total=0,
        test_results=(),
        duration_ms=12,
    )


class TestCodingRunApi:
    """Tests for POST /interview/{id}/coding/run."""

    def test_run_persists_attempt(self, client, isolated_db):
        """Run endpoint stores an attempt and returns the mirror payload."""
        interview_id, task_id = seed_active_coding_interview("coding-run-1")
        with patch(
            "app.coding.services.run_execution.CodingRunnerService.run_public_tests",
            new=AsyncMock(return_value=_success_run_result()),
        ):
            response = client.post(
                f"/interview/{interview_id}/coding/run",
                json={"task_id": task_id, "source_code": "def solve():\n    return 1"},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["attempt_no"] == 1
        assert payload["status"] == "success"
        assert payload["tests_passed"] == 0
        assert payload["attempt_id"] > 0

    def test_run_rejects_wrong_task(self, client, isolated_db):
        """Run fails when the client targets a non-current task."""
        interview_id, _task_id = seed_active_coding_interview("coding-run-2")
        response = client.post(
            f"/interview/{interview_id}/coding/run",
            json={"task_id": "other-task", "source_code": "pass"},
        )
        assert response.status_code == 400

    def test_run_rate_limit(self, client, isolated_db, monkeypatch):
        """Run returns 429 when the per-task attempt limit is exceeded."""
        interview_id, task_id = seed_active_coding_interview("coding-run-3")
        monkeypatch.setenv("CODING_MAX_RUNS_PER_TASK", "1")
        with patch(
            "app.coding.services.run_execution.CodingRunnerService.run_public_tests",
            new=AsyncMock(return_value=_success_run_result()),
        ):
            first = client.post(
                f"/interview/{interview_id}/coding/run",
                json={"task_id": task_id, "source_code": "pass"},
            )
            second = client.post(
                f"/interview/{interview_id}/coding/run",
                json={"task_id": task_id, "source_code": "pass"},
            )
        assert first.status_code == 200
        assert second.status_code == 429

    def test_run_rechecks_current_task_after_judge0(self, client, isolated_db):
        """Run is rejected if the task is completed before persistence."""
        interview_id, task_id = seed_active_coding_interview("coding-run-race")

        async def complete_task_before_return(**_kwargs):
            with InterviewUnitOfWork(auto_commit=True) as uow:
                task = uow.session.query(CodingTask).filter_by(task_id=task_id).one()
                task.submitted_code = "already submitted"
            return _success_run_result()

        with patch(
            "app.coding.services.run_execution.CodingRunnerService.run_public_tests",
            new=AsyncMock(side_effect=complete_task_before_return),
        ):
            response = client.post(
                f"/interview/{interview_id}/coding/run",
                json={"task_id": task_id, "source_code": "pass"},
            )

        assert response.status_code == 400


class TestCodingStateApi:
    """Tests for GET /interview/{id}/coding/state."""

    def test_state_returns_current_task_and_attempts(self, client, isolated_db):
        """State endpoint exposes progress and persisted Run history."""
        interview_id, task_id = seed_active_coding_interview("coding-state-1")
        with patch(
            "app.coding.services.run_execution.CodingRunnerService.run_public_tests",
            new=AsyncMock(return_value=_success_run_result()),
        ):
            client.post(
                f"/interview/{interview_id}/coding/run",
                json={"task_id": task_id, "source_code": "print(1)"},
            )

        response = client.get(f"/interview/{interview_id}/coding/state")
        assert response.status_code == 200
        payload = response.json()
        assert payload["section_status"] == "active"
        assert payload["current_task"]["task_id"] == task_id
        assert payload["run_attempts"][0]["attempt_no"] == 1
        assert "expected_stdout" not in str(payload["current_task"]["task_spec"])

    def test_state_missing_section_returns_404(self, client, isolated_db):
        """State returns 404 when the interview has no coding section."""
        del isolated_db
        response = client.get("/interview/missing-session/coding/state")
        assert response.status_code == 404


class TestCodingWebSocket:
    """Tests for WS /interview/{id}/coding/ws."""

    def test_submit_streams_saved_evaluating_and_feedback(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """Submit persists code, evaluates with AI, and returns feedback."""
        interview_id, task_id = seed_active_coding_interview("coding-ws-1")
        override_ws_ai_provider(client, [])
        evaluation = CodingAnswerEvaluation(
            score=4,
            feedback="Nice work.",
            follow_up_needed=False,
            follow_up_question=None,
            follow_up_mode=None,
        )
        with (
            patch(
                "app.coding.services.submission.CodingRunnerService.run_hidden_tests",
                new=AsyncMock(return_value=_success_run_result()),
            ),
            patch(
                "app.coding.services.submission.CodingEvaluatorService.evaluate_submission",
                new=AsyncMock(return_value=(evaluation, False, None, None)),
            ),
            client.websocket_connect(f"/interview/{interview_id}/coding/ws") as ws,
        ):
            ws.send_json(
                {
                    "type": "submit",
                    "task_id": task_id,
                    "source_code": "def process(data):\n    return data",
                }
            )
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            feedback = ws.receive_json()
            assert feedback["type"] == "feedback"
            assert feedback["task_id"] == task_id
            assert feedback["feedback"] == "Nice work."

    def test_submit_requires_fields(self, client, isolated_db, override_ws_ai_provider):
        """Submit rejects messages without task_id or source_code."""
        interview_id, _task_id = seed_active_coding_interview("coding-ws-2")
        override_ws_ai_provider(client, [])
        with client.websocket_connect(f"/interview/{interview_id}/coding/ws") as ws:
            ws.send_json({"type": "submit", "task_id": "cod-001"})
            error = ws.receive_json()
            assert error["type"] == "error"

    def test_timeout_marks_current_task_as_zero_score(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """Expired coding timers submit the round with zero score."""
        interview_id, task_id = seed_active_coding_interview("coding-ws-timeout")
        with InterviewUnitOfWork(auto_commit=True) as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            assert section is not None
            row = uow.session.query(CodingTask).filter_by(task_id=task_id).one()
            db_section = row.coding_section
            db_section.task_time_limit_seconds = 1
            row.started_at = datetime.now(UTC) - timedelta(seconds=5)

        override_ws_ai_provider(client, [])
        with client.websocket_connect(f"/interview/{interview_id}/coding/ws") as ws:
            ws.send_json({"type": "timeout", "task_id": task_id, "round": 0})
            feedback = ws.receive_json()

        assert feedback["type"] == "feedback"
        assert feedback["task_id"] == task_id
        assert feedback["feedback"]
        with InterviewUnitOfWork() as uow:
            task = uow.session.query(CodingTask).filter_by(task_id=task_id).one()
            assert task.submitted_code == "[Time expired]"
            assert task.score == 0
