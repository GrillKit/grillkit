# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Build client-safe coding task specs from YAML bank rows."""

from __future__ import annotations

from typing import Any

from app.shared.coding import CodingTask as BankCodingTask


def task_spec_from_bank_task(task: BankCodingTask) -> dict[str, Any]:
    """Serialize a coding bank row for persistence and UI.

    Public tests include stdin and expected stdout for server-side Judge0 runs.
    Hidden tests are never serialized here.

    Args:
        task: Loaded row from ``app.shared.coding``.

    Returns:
        JSON-serializable task specification for ``coding_tasks.task_spec``.
    """
    spec = task.coding
    return {
        "language": spec.language,
        "evaluation_mode": spec.evaluation_mode,
        "starter_code": spec.starter_code,
        "entrypoint": spec.entrypoint,
        "public_tests": [
            {
                "name": test_case.name,
                "stdin": test_case.stdin,
                "expected_stdout": test_case.expected_stdout,
            }
            for test_case in spec.public_tests
        ],
        "time_limit_seconds": spec.time_limit_seconds,
        "memory_limit_kb": spec.memory_limit_kb,
        "hidden_tests": [
            {
                "name": test_case.name,
                "stdin": test_case.stdin,
                "expected_stdout": test_case.expected_stdout,
            }
            for test_case in spec.hidden_tests
        ],
        "expected_points": list(task.expected_points),
    }


def client_task_spec_from_stored(spec: dict[str, Any]) -> dict[str, Any]:
    """Strip server-only test expectations from a persisted task spec.

    Args:
        spec: Task spec loaded from ``coding_tasks.task_spec``.

    Returns:
        Client-safe task metadata for UI state responses.
    """
    client_spec = dict(spec)
    client_spec.pop("hidden_tests", None)
    public_tests = spec.get("public_tests")
    if isinstance(public_tests, list):
        client_spec["public_tests"] = [
            {"name": test_case["name"]}
            for test_case in public_tests
            if isinstance(test_case, dict) and "name" in test_case
        ]
    return client_spec
