# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persist coding Run attempts after Judge0 execution."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Any

from app.coding.domain.entities import CodeRunAttempt
from app.coding.domain.exceptions import (
    CodingRunLimitExceededError,
    CodingSectionNotFoundError,
)
from app.coding.domain.value_objects import CodingRunResult, TestCaseRunResult
from app.coding.services.runner import CodingRunnerService
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork


def _max_runs_per_task() -> int:
    """Return the configured Run attempt limit per coding task.

    Returns:
        Positive integer limit from ``CODING_MAX_RUNS_PER_TASK``.
    """
    raw = os.environ.get("CODING_MAX_RUNS_PER_TASK", "20").strip()
    try:
        value = int(raw)
    except ValueError:
        return 20
    return max(1, value)


def _ensure_interview_active(interview_id: str) -> None:
    """Ensure the parent interview session accepts coding actions.

    Args:
        interview_id: Parent interview UUID.

    Raises:
        InterviewNotFoundError: If the interview does not exist.
        InterviewNotActiveError: If the interview is completed.
    """
    with InterviewUnitOfWork() as uow:
        aggregate = uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            raise InterviewNotFoundError(interview_id)
        aggregate.ensure_active()


def _serialize_test_result(result: TestCaseRunResult) -> dict[str, Any]:
    """Convert a domain test result into an API/persistence payload.

    Args:
        result: One public test execution result.

    Returns:
        JSON-serializable dict for clients and persistence.
    """
    payload: dict[str, Any] = {
        "name": result.name,
        "passed": result.passed,
        "expected_stdout": result.expected_stdout,
        "actual_stdout": result.actual_stdout,
    }
    if result.stderr:
        payload["stderr"] = result.stderr
    if result.compile_output:
        payload["compile_output"] = result.compile_output
    if result.judge0_status_description:
        payload["status"] = result.judge0_status_description
    return payload


def coding_run_result_to_summary(result: CodingRunResult) -> dict[str, Any]:
    """Serialize a Judge0 run result for submit_test_summary persistence.

    Args:
        result: Aggregated run outcome from Judge0.

    Returns:
        JSON-serializable hidden test summary payload.
    """
    return {
        "status": result.status,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "compile_output": result.compile_output,
        "tests_passed": result.tests_passed,
        "tests_total": result.tests_total,
        "test_results": [
            _serialize_test_result(test_result) for test_result in result.test_results
        ],
        "duration_ms": result.duration_ms,
    }


class CodingRunExecutionService:
    """Validate, execute, and persist coding Run attempts."""

    @staticmethod
    def _load_run_context(
        interview_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Validate the active task and return execution context.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID for the active coding round.

        Returns:
            Task spec used for public test execution.

        Raises:
            CodingSectionNotFoundError: If no coding section exists.
            CodingSectionNotActiveError: If the coding section is not active.
            CodingTaskNotCurrentError: If ``task_id`` is not the active task.
            CodingRunLimitExceededError: If the per-task Run limit is reached.
        """
        with InterviewUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                raise CodingSectionNotFoundError(interview_id)
            section.ensure_active()
            current_task = section.require_current_task(task_id)
            limit = _max_runs_per_task()
            attempt_count = uow.code_run_attempts.count_for_task(current_task.id)
            if attempt_count >= limit:
                raise CodingRunLimitExceededError(task_id, limit)
            return dict(current_task.task_spec)

    @staticmethod
    async def run_and_persist(
        *,
        interview_id: str,
        task_id: str,
        source_code: str,
    ) -> CodeRunAttempt:
        """Execute public tests and persist an immutable Run attempt.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID for the active coding round.
            source_code: Current Monaco editor contents.

        Returns:
            Persisted domain run attempt.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is completed.
            CodingSectionNotFoundError: If no coding section exists.
            CodingSectionNotActiveError: If the coding section is not active.
            CodingTaskNotCurrentError: If ``task_id`` is not the active task.
            CodingRunLimitExceededError: If the per-task Run limit is reached.
        """
        _ensure_interview_active(interview_id)
        task_spec = CodingRunExecutionService._load_run_context(interview_id, task_id)
        run_result = await CodingRunnerService.run_public_tests(
            source_code=source_code,
            task_spec=task_spec,
        )
        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            aggregate.ensure_active()
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                raise CodingSectionNotFoundError(interview_id)
            section.ensure_active()
            current_task = section.require_current_task(task_id)
            limit = _max_runs_per_task()
            attempt_count = uow.code_run_attempts.count_for_task(current_task.id)
            if attempt_count >= limit:
                raise CodingRunLimitExceededError(task_id, limit)
            attempt = CodingRunExecutionService._build_attempt(
                coding_task_id=current_task.id,
                attempt_no=attempt_count + 1,
                source_code=source_code,
                language=str(current_task.task_spec.get("language", "python")),
                run_result=run_result,
            )
            return uow.code_run_attempts.create(attempt)

    @staticmethod
    def _build_attempt(
        *,
        coding_task_id: int,
        attempt_no: int,
        source_code: str,
        language: str,
        run_result: CodingRunResult,
    ) -> CodeRunAttempt:
        """Build a domain run attempt from a Judge0 aggregate result.

        Args:
            coding_task_id: Parent coding task row ID.
            attempt_no: Sequential attempt number for the task.
            source_code: Editor snapshot from the client.
            language: Programming language slug.
            run_result: Aggregated Judge0 outcome.

        Returns:
            Unpersisted domain attempt.
        """
        test_results = tuple(
            _serialize_test_result(result) for result in run_result.test_results
        )
        return CodeRunAttempt(
            id=CodeRunAttempt.NEW_ID,
            coding_task_id=coding_task_id,
            attempt_no=attempt_no,
            source_code=source_code,
            language=language,
            status=run_result.status,
            stdout=run_result.stdout,
            stderr=run_result.stderr,
            compile_output=run_result.compile_output,
            tests_passed=run_result.tests_passed,
            tests_total=run_result.tests_total,
            test_results=test_results,
            duration_ms=run_result.duration_ms,
            created_at=datetime.now(UTC),
        )
