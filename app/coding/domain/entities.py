# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section aggregate entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from app.coding.domain.exceptions import (
    CodingSectionNotActiveError,
    CodingTaskNotCurrentError,
    CodingTaskNotFoundError,
)
from app.coding.domain.value_objects import PlannedCodingTask, RunOutcomeStatus
from app.interview.domain.value_objects import InterviewSelection
from app.shared.section import Section
from app.shared.timed_task import TimedTask

CodingSectionStatus = Literal["pending", "active", "completed", "skipped"]


@dataclass(frozen=True, slots=True)
class CodingTask(TimedTask):
    """One coding task round within a coding section.

    Attributes:
        id: Task row primary key.
        coding_section_id: Parent coding section ID.
        interview_id: Parent interview UUID (denormalized from the section).
        task_id: YAML task ID from the coding bank.
        order: Display order within the section (1-based).
        round: Follow-up round number (0 = initial).
        prompt_text: Task prompt snapshot.
        task_spec: Client-safe task metadata JSON.
        submitted_code: Final submitted source code, or None when pending.
        submit_test_summary: Hidden test results after submit, or None.
        score: AI score for the round, or None when not evaluated.
        feedback: AI-generated feedback text, or None.
        started_at: When the per-task timer started, or None.
        created_at: When this task row was created.
    """

    TIME_EXPIRED_SOURCE_CODE = "[Time expired]"
    NEW_ID = 0

    id: int
    coding_section_id: int
    interview_id: str
    task_id: str
    order: int
    round: int
    prompt_text: str
    task_spec: dict[str, Any]
    submitted_code: str | None
    submit_test_summary: dict[str, Any] | None
    score: int | None
    feedback: str | None
    started_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CodingSection(Section[CodingTask]):
    """Coding section aggregate root.

    Attributes:
        id: Coding section primary key.
        interview_id: Parent interview UUID.
        locale: Language code for feedback.
        selection: Parsed coding-bank selection for this section.
        task_count: Number of coding tasks in this section.
        task_ids: Task IDs in display order.
        task_time_limit_seconds: Per-task time limit, or None when disabled.
        status: Section status.
        section_score: Aggregated section score when evaluated.
        section_feedback: Parsed section evaluation payload.
        tasks: Coding tasks in display order (order, then round).
    """

    MAX_SCORE_PER_ROUND = 5  # pyright: ignore
    NEW_ID = 0

    id: int
    interview_id: str
    locale: str
    selection: InterviewSelection
    task_count: int
    task_ids: tuple[str, ...]
    task_time_limit_seconds: int | None
    status: CodingSectionStatus
    section_score: int | None
    section_feedback: dict[str, object] | None
    tasks: tuple[CodingTask, ...]

    # ------------------------------------------------------------------
    # Section abstract hooks
    # ------------------------------------------------------------------
    @property
    def _completion_field_name(self) -> str:
        return "submitted_code"

    @property
    def _task_id_field(self) -> str:
        return "task_id"

    def _task_not_found_error(self, task_id: str, round_num: int) -> Exception:
        return CodingTaskNotFoundError(self.interview_id, task_id, round_num)

    def _timeout_replacement_fields(
        self, task: CodingTask, feedback: str
    ) -> dict[str, Any]:
        return {
            "submitted_code": CodingTask.TIME_EXPIRED_SOURCE_CODE,
            "submit_test_summary": {"status": "timeout"},
            "score": 0,
            "feedback": feedback,
        }

    def _create_follow_up(
        self,
        base: CodingTask,
        next_round: int,
        prompt_text: str,
        *,
        starter_code: str | None = None,
        **kwargs: Any,
    ) -> CodingTask:
        follow_up_spec = dict(base.task_spec)
        if starter_code is not None:
            follow_up_spec["starter_code"] = starter_code
        return CodingTask(
            id=CodingTask.NEW_ID,
            coding_section_id=self.id,
            interview_id=self.interview_id,
            task_id=base.task_id,
            order=base.order,
            round=next_round,
            prompt_text=prompt_text,
            task_spec=follow_up_spec,
            submitted_code=None,
            submit_test_summary=None,
            score=None,
            feedback=None,
            started_at=None,
            created_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def start(
        cls,
        interview_id: str,
        *,
        selection: InterviewSelection,
        locale: str,
        planned_tasks: tuple[PlannedCodingTask, ...],
        task_time_limit_seconds: int | None = None,
        coding_section_id: int = NEW_ID,
        status: CodingSectionStatus = "active",
    ) -> CodingSection:
        """Build a new coding section from a planned task list.

        Args:
            interview_id: Parent interview UUID.
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback.
            planned_tasks: Ordered tasks for this section (non-empty).
            task_time_limit_seconds: Per-task time limit, or None to disable.
            coding_section_id: Existing section ID, or ``NEW_ID`` before insert.
            status: Initial section status (``pending`` or ``active``).

        Returns:
            Section aggregate with initial task rows (``CodingTask.NEW_ID``).

        Raises:
            ValueError: If ``planned_tasks`` is empty.
        """
        if not planned_tasks:
            raise ValueError("No coding tasks found for the selected topics")

        when = datetime.now(UTC)
        task_ids = tuple(task.id for task in planned_tasks)
        timer_start = (
            when if task_time_limit_seconds is not None and status == "active" else None
        )
        tasks: list[CodingTask] = []
        for order, planned in enumerate(planned_tasks, start=1):
            tasks.append(
                CodingTask(
                    id=CodingTask.NEW_ID,
                    coding_section_id=coding_section_id,
                    interview_id=interview_id,
                    task_id=planned.id,
                    order=order,
                    round=0,
                    prompt_text=planned.text,
                    task_spec=dict(planned.task_spec),
                    submitted_code=None,
                    submit_test_summary=None,
                    score=None,
                    feedback=None,
                    started_at=timer_start if order == 1 else None,
                    created_at=when,
                )
            )
        return cls(
            id=coding_section_id,
            interview_id=interview_id,
            locale=locale,
            selection=selection,
            task_count=len(planned_tasks),
            task_ids=task_ids,
            task_time_limit_seconds=task_time_limit_seconds,
            status=status,
            section_score=None,
            section_feedback=None,
            tasks=tuple(tasks),
        )

    # ------------------------------------------------------------------
    # Domain-specific behaviour
    # ------------------------------------------------------------------
    def ensure_active(self) -> None:
        """Ensure this coding section accepts submissions.

        Raises:
            CodingSectionNotActiveError: If the section is not in ``active`` status.
        """
        if self.status != "active":
            raise CodingSectionNotActiveError(self.interview_id)

    def find_first_unsubmitted(self) -> CodingTask | None:
        """Return the first task without a submitted solution.

        Returns:
            The first task with ``submitted_code`` unset, or None when all are done.
        """
        return self.find_first_pending()

    def with_submit_test_summary(
        self,
        task_row_id: int,
        summary: dict[str, Any] | None,
        *,
        source_code: str,
    ) -> CodingSection:
        """Return aggregate with submitted code and hidden test summary.

        Args:
            task_row_id: Primary key of the task row to update.
            summary: Hidden test execution summary from Judge0.
            source_code: Final editor contents at submit time.

        Returns:
            A new aggregate with submission fields set on the target task.
        """
        tasks = tuple(
            replace(
                task,
                submitted_code=source_code,
                submit_test_summary=summary,
            )
            if task.id == task_row_id
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def require_current_task(self, task_id: str) -> CodingTask:
        """Return the active unsubmitted task when it matches ``task_id``.

        Args:
            task_id: YAML task ID from a client Run/Submit request.

        Returns:
            The current coding task row.

        Raises:
            CodingTaskNotCurrentError: If no matching unsubmitted task is active.
        """
        current = self.find_first_unsubmitted()
        if current is None or current.task_id != task_id:
            raise CodingTaskNotCurrentError(self.interview_id, task_id)
        return current

    def find_next_unsubmitted_after(self, current_index: int) -> CodingTask | None:
        """Return the next unsubmitted task after a position in the task list.

        Args:
            current_index: Index of the current task in ``tasks``.

        Returns:
            The next unsubmitted task, or None if none remain.
        """
        return self.find_next_pending_after(current_index)


@dataclass(frozen=True, slots=True)
class CodeRunAttempt:
    """Immutable snapshot of one Run action on a coding task.

    Attributes:
        id: Attempt row primary key.
        coding_task_id: Parent coding task row ID.
        attempt_no: Sequential attempt number for the task.
        source_code: Editor contents at Run time.
        language: Programming language slug.
        status: Aggregated run outcome.
        stdout: Captured standard output.
        stderr: Captured standard error.
        compile_output: Compiler output when applicable.
        tests_passed: Number of public tests that passed.
        tests_total: Number of public tests executed.
        test_results: Serialized per-test result payloads.
        duration_ms: Judge0 execution duration in milliseconds.
        created_at: Timestamp when the attempt was recorded.
    """

    NEW_ID = 0

    id: int
    coding_task_id: int
    attempt_no: int
    source_code: str
    language: str
    status: RunOutcomeStatus
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    tests_passed: int
    tests_total: int
    test_results: tuple[dict[str, Any], ...]
    duration_ms: int | None
    created_at: datetime
