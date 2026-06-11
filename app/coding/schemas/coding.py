# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section read models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from app.coding.domain.entities import CodeRunAttempt, CodingSectionStatus
from app.coding.domain.value_objects import RunOutcomeStatus


@dataclass(frozen=True, slots=True)
class CodingTaskRead:
    """Read model for one coding task row.

    Attributes:
        id: Task primary key.
        task_id: YAML task ID.
        order: Display order within the section.
        round: Follow-up round number.
        prompt_text: Task prompt snapshot.
        task_spec: Client-safe task metadata.
        submitted_code: Submitted source code, if any.
        score: AI score for the round.
        feedback: AI feedback text.
        started_at: Timer start timestamp.
    """

    id: int
    task_id: str
    order: int
    round: int
    prompt_text: str
    task_spec: dict[str, Any]
    submitted_code: str | None
    score: int | None
    feedback: str | None
    started_at: datetime | None


@dataclass(frozen=True, slots=True)
class CodingSectionRead:
    """Read model for a coding section aggregate.

    Attributes:
        id: Section primary key.
        interview_id: Parent interview UUID.
        status: Section status.
        locale: Locale for feedback.
        selection_spec: JSON selection for this section.
        task_count: Number of tasks in the section.
        task_time_limit_seconds: Per-task timer, if enabled.
        tasks: Coding tasks in display order.
        section_score: Aggregated section score.
        section_feedback: Cached section narrative feedback.
    """

    id: int
    interview_id: str
    status: CodingSectionStatus
    locale: str
    selection_spec: str
    task_count: int
    task_time_limit_seconds: int | None
    tasks: list[CodingTaskRead]
    section_score: int | None
    section_feedback: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class CodeRunAttemptRead:
    """Read model for one persisted Run attempt.

    Attributes:
        attempt_id: Attempt row primary key.
        attempt_no: Sequential attempt number for the task.
        status: Aggregated run outcome.
        stdout: Captured standard output.
        stderr: Captured standard error.
        compile_output: Compiler output when applicable.
        tests_passed: Number of public tests that passed.
        tests_total: Number of public tests executed.
        test_results: Per-test result payloads.
        duration_ms: Judge0 execution duration in milliseconds.
        created_at: Timestamp when the attempt was recorded.
    """

    attempt_id: int
    attempt_no: int
    status: RunOutcomeStatus
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    tests_passed: int
    tests_total: int
    test_results: list[dict[str, Any]]
    duration_ms: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CodingTaskStateRead:
    """Client-safe coding task row for session state responses.

    Attributes:
        id: Task row primary key.
        task_id: YAML task ID.
        order: Display order within the section.
        round: Follow-up round number.
        prompt_text: Task prompt snapshot.
        task_spec: Client-safe task metadata.
        submitted_code: Submitted source code, if any.
        score: AI score for the round.
        feedback: AI feedback text.
        started_at: Timer start timestamp.
    """

    id: int
    task_id: str
    order: int
    round: int
    prompt_text: str
    task_spec: dict[str, Any]
    submitted_code: str | None
    score: int | None
    feedback: str | None
    started_at: datetime | None


@dataclass(frozen=True, slots=True)
class CodingSessionStateRead:
    """Read model for ``GET /interview/{id}/coding/state``.

    Attributes:
        interview_id: Parent interview UUID.
        section_status: Coding section status.
        task_time_limit_seconds: Per-task timer, if enabled.
        completed_tasks: Number of submitted tasks.
        total_tasks: Total tasks in the section.
        current_task: Active unsubmitted task, if any.
        tasks: All task rows in display order.
        run_attempts: Run history for the current task.
    """

    interview_id: str
    section_status: CodingSectionStatus
    task_time_limit_seconds: int | None
    completed_tasks: int
    total_tasks: int
    current_task: CodingTaskStateRead | None
    tasks: list[CodingTaskStateRead]
    run_attempts: list[CodeRunAttemptRead]


class CodingRunRequest(BaseModel):
    """Request body for ``POST /interview/{id}/coding/run``."""

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(min_length=1)
    source_code: str


class CodingRunResponse(BaseModel):
    """Response body mirroring a persisted Run attempt."""

    model_config = ConfigDict(frozen=True)

    attempt_id: int
    attempt_no: int
    status: RunOutcomeStatus
    stdout: str | None = None
    stderr: str | None = None
    compile_output: str | None = None
    tests_passed: int
    tests_total: int
    test_results: list[dict[str, Any]]
    duration_ms: int | None = None


def domain_run_attempt_to_read(attempt: CodeRunAttempt) -> CodeRunAttemptRead:
    """Map a domain run attempt entity to a read model.

    Args:
        attempt: Persisted domain attempt.

    Returns:
        API read model for Run responses and state payloads.
    """
    return CodeRunAttemptRead(
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        stdout=attempt.stdout,
        stderr=attempt.stderr,
        compile_output=attempt.compile_output,
        tests_passed=attempt.tests_passed,
        tests_total=attempt.tests_total,
        test_results=list(attempt.test_results),
        duration_ms=attempt.duration_ms,
        created_at=attempt.created_at,
    )


def run_attempt_to_response(attempt: CodeRunAttemptRead) -> CodingRunResponse:
    """Convert a run attempt read model to an API response.

    Args:
        attempt: Persisted attempt read model.

    Returns:
        Pydantic response payload for the Run endpoint.
    """
    return CodingRunResponse(
        attempt_id=attempt.attempt_id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        stdout=attempt.stdout,
        stderr=attempt.stderr,
        compile_output=attempt.compile_output,
        tests_passed=attempt.tests_passed,
        tests_total=attempt.tests_total,
        test_results=attempt.test_results,
        duration_ms=attempt.duration_ms,
    )


def _json_safe(value: Any) -> Any:
    """Recursively convert datetimes to ISO strings for JSON responses.

    Args:
        value: Arbitrary nested value from a dataclass ``asdict`` payload.

    Returns:
        JSON-serializable value.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def coding_state_to_dict(state: CodingSessionStateRead) -> dict[str, Any]:
    """Serialize a coding session state read model for JSON responses.

    Args:
        state: Session state read model.

    Returns:
        JSON-serializable dict.
    """
    return cast(dict[str, Any], _json_safe(asdict(state)))
