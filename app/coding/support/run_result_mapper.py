# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Map Judge0 run results to persistence-friendly summaries."""

from __future__ import annotations

from typing import Any

from app.coding.domain.value_objects import CaseRunResult, CodingRunResult


class Judge0ResultMapper:
    """Serialize Judge0 run results for persistence."""

    @staticmethod
    def _serialize_test_result(result: CaseRunResult) -> dict[str, Any]:
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

    @staticmethod
    def to_summary(result: CodingRunResult) -> dict[str, Any]:
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
                Judge0ResultMapper._serialize_test_result(test_result)
                for test_result in result.test_results
            ],
            "duration_ms": result.duration_ms,
        }
