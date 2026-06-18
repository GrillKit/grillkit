# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Full flow tests for coding: run → submit (WS) → next task → finish."""

from unittest.mock import AsyncMock, patch

from app.coding.domain.value_objects import CodingRunResult
from app.coding.services.evaluator.models import CodingAnswerEvaluation
from app.interview.repositories.uow import InterviewUnitOfWork
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


class TestCodingFullFlow:
    """Run, submit, and navigate through a coding section."""

    def test_run_then_submit_then_next_task(
        self, client, isolated_db, mock_judge0, override_ws_ai_provider
    ):
        """Submit after Run; score and feedback returned; next task loaded."""
        interview_id, task_id = seed_active_coding_interview(
            "coding-full-1", task_ids=["cod-001", "cod-002"]
        )

        mock_judge0()  # default success
        evaluation = CodingAnswerEvaluation(
            score=4,
            feedback="Nice work.",
            follow_up_needed=False,
            follow_up_question=None,
            follow_up_mode=None,
        )

        # 1. Run (public tests / compile)
        response = client.post(
            f"/interview/{interview_id}/coding/run",
            json={"task_id": task_id, "source_code": "def solve():\n    return 42"},
        )
        assert response.status_code == 200
        run_result = response.json()
        assert run_result["status"] == "success"
        assert run_result["attempt_no"] == 1

        # 2. Submit via WS
        override_ws_ai_provider(client, [])
        with (
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
                    "source_code": "def solve():\n    return 42",
                }
            )
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb = ws.receive_json()
            assert fb["type"] == "feedback"
            assert fb["task_id"] == task_id
            assert fb["feedback"] == "Nice work."

        # 3. State should show submitted + next task
        state = client.get(f"/interview/{interview_id}/coding/state").json()
        assert state["completed_tasks"] == 1
        assert state["current_task"]["task_id"] == "cod-002"

    def test_run_compile_error_shows_error(self, client, isolated_db, mock_judge0):
        """Run with compile error returns proper error status."""
        interview_id, task_id = seed_active_coding_interview("coding-compile-1")
        mock_judge0(status="compile_error")

        response = client.post(
            f"/interview/{interview_id}/coding/run",
            json={"task_id": task_id, "source_code": "def solve(\n    return"},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "compile_error"

    def test_finish_section_after_all_tasks(
        self, client, isolated_db, mock_judge0, override_ws_ai_provider
    ):
        """All tasks submitted → coding section completed."""
        interview_id, task_id = seed_active_coding_interview(
            "coding-finish-1", task_ids=["cod-001"]
        )
        mock_judge0()
        evaluation = CodingAnswerEvaluation(
            score=5,
            feedback="Perfect.",
            follow_up_needed=False,
            follow_up_question=None,
            follow_up_mode=None,
        )

        override_ws_ai_provider(client, [])
        with (
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
                    "source_code": "def solve(): return 42",
                }
            )
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb = ws.receive_json()
            assert fb["type"] == "feedback"
            # next_task should be None (last task) — omitted entirely when None by serializer
            assert fb.get("next_task") is None

        # Section should be completed
        with InterviewUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            assert section is not None
            assert section.is_complete()

    def test_run_attempts_limit(self, client, isolated_db, mock_judge0, monkeypatch):
        """Run returns 429 after exceeding max attempts."""
        monkeypatch.setenv("CODING_MAX_RUNS_PER_TASK", "1")
        interview_id, task_id = seed_active_coding_interview("coding-limit-1")
        mock_judge0()

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
