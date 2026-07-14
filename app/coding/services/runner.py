# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Execute coding task submissions through Judge0."""

from __future__ import annotations

from typing import Any

from app.coding.domain.value_objects import (
    CaseRunResult,
    CodingRunResult,
    RunOutcomeStatus,
)
from app.coding.services.harness import build_python_script
from app.coding.services.judge0_client import (
    JUDGE0_STATUS_ACCEPTED,
    JUDGE0_STATUS_COMPILATION_ERROR,
    JUDGE0_STATUS_RUNTIME_ERROR,
    JUDGE0_STATUS_TIME_LIMIT,
    Judge0Client,
    Judge0SubmissionResult,
)
from app.coding.services.judge0_config import judge0_language_id


class CodingRunnerService:
    """Run public tests and compile-only checks for coding tasks."""

    @staticmethod
    async def run_hidden_tests(
        *,
        source_code: str,
        task_spec: dict[str, Any],
        client: Judge0Client | None = None,
    ) -> CodingRunResult:
        """Execute hidden tests for a coding submission.

        Args:
            source_code: Submitted editor contents.
            task_spec: Persisted task metadata including ``hidden_tests``.
            client: Optional Judge0 client for dependency injection in tests.

        Returns:
            Aggregated hidden test outcome.
        """
        hidden_tests = task_spec.get("hidden_tests")
        if not isinstance(hidden_tests, list) or not hidden_tests:
            return await CodingRunnerService.run_public_tests(
                source_code=source_code,
                task_spec={**task_spec, "evaluation_mode": "ai"},
                client=client,
            )
        hidden_spec = {
            **task_spec,
            "evaluation_mode": "tests",
            "public_tests": hidden_tests,
        }
        return await CodingRunnerService.run_public_tests(
            source_code=source_code,
            task_spec=hidden_spec,
            client=client,
        )

    @staticmethod
    async def run_public_tests(
        *,
        source_code: str,
        task_spec: dict[str, Any],
        client: Judge0Client | None = None,
    ) -> CodingRunResult:
        """Execute public tests for a coding task, or compile-only for AI tasks.

        Args:
            source_code: Current editor contents from the candidate.
            task_spec: Persisted task metadata with language, mode, and tests.
            client: Optional Judge0 client for dependency injection in tests.

        Returns:
            Aggregated run outcome with per-test details.
        """
        judge0 = client or Judge0Client.from_env()
        language = str(task_spec.get("language", "python"))
        language_id = judge0_language_id(language)
        evaluation_mode = str(task_spec.get("evaluation_mode", "tests"))
        cpu_time_limit = task_spec.get("time_limit_seconds")
        memory_limit_kb = task_spec.get("memory_limit_kb")
        entrypoint = task_spec.get("entrypoint")
        if not isinstance(entrypoint, str):
            entrypoint = None

        if evaluation_mode == "ai":
            return await CodingRunnerService._run_compile_only(
                source_code=source_code,
                language_id=language_id,
                entrypoint=entrypoint,
                cpu_time_limit=cpu_time_limit,
                memory_limit_kb=memory_limit_kb,
                client=judge0,
            )

        public_tests = task_spec.get("public_tests") or []
        if not isinstance(public_tests, list) or not public_tests:
            return await CodingRunnerService._run_compile_only(
                source_code=source_code,
                language_id=language_id,
                entrypoint=entrypoint,
                cpu_time_limit=cpu_time_limit,
                memory_limit_kb=memory_limit_kb,
                client=judge0,
            )

        results: list[CaseRunResult] = []
        total_duration_ms = 0
        last_stdout: str | None = None
        last_stderr: str | None = None
        last_compile_output: str | None = None

        for raw_test in public_tests:
            if not isinstance(raw_test, dict):
                continue
            name = str(raw_test.get("name", "test"))
            stdin = str(raw_test.get("stdin", ""))
            expected_stdout = str(raw_test.get("expected_stdout", ""))
            script = build_python_script(
                source_code,
                entrypoint=entrypoint,
                stdin=stdin,
            )
            submission = await judge0.submit(
                source_code=script,
                language_id=language_id,
                stdin=stdin,
                cpu_time_limit=float(cpu_time_limit)
                if isinstance(cpu_time_limit, (int, float))
                else None,
                memory_limit_kb=memory_limit_kb
                if isinstance(memory_limit_kb, int)
                else None,
            )
            case_result = CodingRunnerService._case_result_from_submission(
                name=name,
                expected_stdout=expected_stdout,
                submission=submission,
            )
            results.append(case_result)
            if submission.duration_ms is not None:
                total_duration_ms += submission.duration_ms
            last_stdout = submission.stdout
            last_stderr = submission.stderr
            last_compile_output = submission.compile_output
            if not case_result.passed:
                break

        tests_passed = sum(1 for result in results if result.passed)
        tests_total = len(results)
        status = CodingRunnerService._aggregate_status(results)
        return CodingRunResult(
            status=status,
            stdout=last_stdout,
            stderr=last_stderr,
            compile_output=last_compile_output,
            tests_passed=tests_passed,
            tests_total=tests_total,
            test_results=tuple(results),
            duration_ms=total_duration_ms or None,
        )

    @staticmethod
    async def _run_compile_only(
        *,
        source_code: str,
        language_id: int,
        entrypoint: str | None,
        cpu_time_limit: Any,
        memory_limit_kb: Any,
        client: Judge0Client,
    ) -> CodingRunResult:
        """Compile candidate code without executing public tests.

        Args:
            source_code: Candidate editor contents.
            language_id: Judge0 language identifier.
            entrypoint: Optional callable used by the harness wrapper.
            cpu_time_limit: Optional per-task CPU limit in seconds.
            memory_limit_kb: Optional memory limit in kilobytes.
            client: Judge0 client instance.

        Returns:
            Compile-only run result.
        """
        script = build_python_script(source_code, entrypoint=entrypoint)
        submission = await client.submit(
            source_code=script,
            language_id=language_id,
            cpu_time_limit=float(cpu_time_limit)
            if isinstance(cpu_time_limit, (int, float))
            else None,
            memory_limit_kb=memory_limit_kb
            if isinstance(memory_limit_kb, int)
            else None,
            compile_only=True,
        )
        status = CodingRunnerService._status_from_submission(submission, passed=True)
        return CodingRunResult(
            status=status,
            stdout=submission.stdout,
            stderr=submission.stderr,
            compile_output=submission.compile_output,
            tests_passed=0,
            tests_total=0,
            test_results=(),
            duration_ms=submission.duration_ms,
        )

    @staticmethod
    def _case_result_from_submission(
        *,
        name: str,
        expected_stdout: str,
        submission: Judge0SubmissionResult,
    ) -> CaseRunResult:
        """Map one Judge0 submission to a public test case result.

        Args:
            name: Test case name.
            expected_stdout: Expected stdout for the case.
            submission: Judge0 response for the case.

        Returns:
            Per-test run result.
        """
        actual_stdout = submission.stdout or ""
        passed = (
            submission.status_id == JUDGE0_STATUS_ACCEPTED
            and actual_stdout == expected_stdout
        )
        return CaseRunResult(
            name=name,
            passed=passed,
            expected_stdout=expected_stdout,
            actual_stdout=actual_stdout,
            stderr=submission.stderr,
            compile_output=submission.compile_output,
            judge0_status_id=submission.status_id,
            judge0_status_description=submission.status_description,
        )

    @staticmethod
    def _status_from_submission(
        submission: Judge0SubmissionResult,
        *,
        passed: bool,
    ) -> RunOutcomeStatus:
        """Derive a high-level run status from a Judge0 submission.

        Args:
            submission: Judge0 response.
            passed: Whether the caller considers the case successful.

        Returns:
            Aggregated run status slug.
        """
        status_id = submission.status_id
        if status_id == JUDGE0_STATUS_COMPILATION_ERROR:
            return "compile_error"
        if status_id == JUDGE0_STATUS_TIME_LIMIT:
            return "time_limit_exceeded"
        if status_id == JUDGE0_STATUS_RUNTIME_ERROR:
            return "runtime_error"
        if passed:
            return "success"
        return "tests_failed"

    @staticmethod
    def _aggregate_status(results: list[CaseRunResult]) -> RunOutcomeStatus:
        """Derive the aggregate run status from per-test results.

        Args:
            results: Executed public test results in order.

        Returns:
            Aggregate run status slug.
        """
        if not results:
            return "success"
        if any(
            result.judge0_status_id == JUDGE0_STATUS_COMPILATION_ERROR
            for result in results
        ):
            return "compile_error"
        if any(
            result.judge0_status_id == JUDGE0_STATUS_TIME_LIMIT for result in results
        ):
            return "time_limit_exceeded"
        if any(
            result.judge0_status_id == JUDGE0_STATUS_RUNTIME_ERROR for result in results
        ):
            return "runtime_error"
        if all(result.passed for result in results):
            return "success"
        return "tests_failed"
