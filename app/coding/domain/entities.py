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
from app.shared.task_timer import (
    DEFAULT_TIMEOUT_GRACE_SECONDS,
)
from app.shared.task_timer import (
    is_timer_expired as shared_is_timer_expired,
)
from app.shared.task_timer import (
    remaining_seconds as shared_remaining_seconds,
)
from app.shared.task_timer import (
    timer_deadline as shared_timer_deadline,
)

CodingSectionStatus = Literal["pending", "active", "completed", "skipped"]


@dataclass(frozen=True, slots=True)
class CodingTask:
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
    TIMEOUT_GRACE_SECONDS = DEFAULT_TIMEOUT_GRACE_SECONDS
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

    def timer_deadline(self, limit_seconds: int) -> datetime:
        """Compute the absolute deadline for this timed task round.

        Args:
            limit_seconds: Allowed duration in seconds.

        Returns:
            Timezone-aware deadline timestamp.

        Raises:
            ValueError: If the round has no ``started_at`` timestamp.
        """
        if self.started_at is None:
            raise ValueError("Coding task round has no started_at")
        return shared_timer_deadline(
            self.started_at,
            limit_seconds,
            label="Coding task",
        )

    def is_timer_expired(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
        *,
        grace_seconds: int = TIMEOUT_GRACE_SECONDS,
    ) -> bool:
        """Return whether the per-task timer has elapsed.

        Args:
            limit_seconds: Configured limit for the section (None disables timer).
            now: Current time (defaults to UTC now).
            grace_seconds: Extra seconds allowed for network delay on timeout submit.

        Returns:
            True if the timer is enabled and the deadline plus grace has passed.
        """
        return shared_is_timer_expired(
            self.started_at,
            limit_seconds,
            now,
            grace_seconds=grace_seconds,
        )

    def remaining_seconds(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
    ) -> int | None:
        """Return whole seconds left on the timer, or None if disabled.

        Args:
            limit_seconds: Configured limit for the section.
            now: Current time (defaults to UTC now).

        Returns:
            Non-negative seconds remaining, or None when the timer is off.
        """
        return shared_remaining_seconds(self.started_at, limit_seconds, now)

    def client_timeout_due(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a client-sent timeout should be accepted."""
        if limit_seconds is None or self.started_at is None:
            return False
        rem = self.remaining_seconds(limit_seconds, now)
        return self.is_timer_expired(limit_seconds, now, grace_seconds=0) or (
            rem is not None and rem <= 0
        )


@dataclass(frozen=True, slots=True)
class CodingSection:
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

    MAX_SCORE_PER_ROUND = 5
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

    def with_activated(self) -> CodingSection:
        """Return aggregate with ``pending`` status promoted to ``active``.

        Returns:
            Updated aggregate when status was ``pending``, otherwise ``self``.
        """
        if self.status != "pending":
            return self
        return replace(self, status="active")

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
        for task in self.tasks:
            if task.submitted_code is None:
                return task
        return None

    def is_complete(self) -> bool:
        """Return whether every task in this section has been submitted.

        Returns:
            True when there is at least one task and none remain unsubmitted.
        """
        return bool(self.tasks) and self.find_first_unsubmitted() is None

    def total_score(self) -> int:
        """Sum scores from all submitted task rounds in this section.

        Returns:
            Total earned points across submitted rounds.
        """
        return sum(
            (task.score or 0) for task in self.tasks if task.submitted_code is not None
        )

    def max_score(self) -> int:
        """Compute maximum achievable score for submitted rounds.

        Returns:
            Maximum possible points for rounds with submissions.
        """
        submitted_rounds = sum(
            1 for task in self.tasks if task.submitted_code is not None
        )
        return self.MAX_SCORE_PER_ROUND * submitted_rounds

    def with_cached_section_feedback(
        self,
        feedback: dict[str, object],
        *,
        section_score: int,
    ) -> CodingSection:
        """Return aggregate with prefetched section feedback when not cached.

        Args:
            feedback: Parsed section evaluation payload.
            section_score: Aggregated section score.

        Returns:
            Updated aggregate, or ``self`` when feedback is already cached.
        """
        if self.section_feedback is not None:
            return self
        return replace(
            self,
            section_feedback=feedback,
            section_score=section_score,
        )

    def start_timer_for_task(
        self, task_row_id: int, when: datetime | None = None
    ) -> CodingSection:
        """Start the per-task timer on a coding task when the section has a limit.

        Args:
            task_row_id: Primary key of the task row to activate.
            when: Timestamp to set (defaults to UTC now).

        Returns:
            A new aggregate with ``started_at`` set on the target task when applicable.
        """
        if self.task_time_limit_seconds is None:
            return self
        started_at = when or datetime.now(UTC)
        tasks = tuple(
            replace(task, started_at=started_at)
            if task.id == task_row_id and task.started_at is None
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def with_submit_test_summary(
        self,
        task_row_id: int,
        summary: dict[str, Any],
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

    def with_timed_out_round(self, task_row_id: int, feedback: str) -> CodingSection:
        """Return aggregate with a coding round marked as timed out."""
        tasks = tuple(
            replace(
                task,
                submitted_code=CodingTask.TIME_EXPIRED_SOURCE_CODE,
                submit_test_summary={"status": "timeout"},
                score=0,
                feedback=feedback,
            )
            if task.id == task_row_id
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def with_evaluation(
        self,
        task_id: str,
        round_num: int,
        score: int,
        feedback: str,
    ) -> CodingSection:
        """Return aggregate with AI score and feedback on one task round.

        Args:
            task_id: YAML task ID.
            round_num: Follow-up round (0 = initial).
            score: AI score for the round.
            feedback: AI feedback text.

        Returns:
            A new aggregate with evaluation fields set on the target task.
        """
        target = self.find_task(task_id, round_num)
        tasks = tuple(
            replace(task, score=score, feedback=feedback)
            if task.id == target.id
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def max_round_for_task(self, task_id: str) -> int:
        """Return the highest follow-up round number for a bank task ID.

        Args:
            task_id: YAML task ID.

        Returns:
            Maximum ``round`` value among rows for the task, or 0 when none exist.
        """
        rounds = [task.round for task in self.tasks if task.task_id == task_id]
        return max(rounds) if rounds else 0

    def with_follow_up(
        self,
        task_id: str,
        prompt_text: str,
        *,
        starter_code: str | None,
    ) -> tuple[CodingSection, CodingTask]:
        """Return aggregate with a new unsubmitted follow-up task row.

        Args:
            task_id: YAML task ID for the follow-up chain.
            prompt_text: Follow-up prompt shown to the candidate.
            starter_code: Monaco starter code for code-mode follow-ups.

        Returns:
            Tuple of updated aggregate and the pending follow-up task.
        """
        base = self.find_task(task_id, 0)
        next_round = self.max_round_for_task(task_id) + 1
        follow_up_spec = dict(base.task_spec)
        if starter_code is not None:
            follow_up_spec["starter_code"] = starter_code
        created_at = datetime.now(UTC)
        follow_up = CodingTask(
            id=CodingTask.NEW_ID,
            coding_section_id=self.id,
            interview_id=self.interview_id,
            task_id=task_id,
            order=base.order,
            round=next_round,
            prompt_text=prompt_text,
            task_spec=follow_up_spec,
            submitted_code=None,
            submit_test_summary=None,
            score=None,
            feedback=None,
            started_at=None,
            created_at=created_at,
        )
        return replace(self, tasks=self.tasks + (follow_up,)), follow_up

    def find_next_unsubmitted_after(self, current_index: int) -> CodingTask | None:
        """Return the next unsubmitted task after a position in the task list.

        Args:
            current_index: Index of the current task in ``tasks``.

        Returns:
            The next unsubmitted task, or None if none remain.
        """
        for task in self.tasks[current_index + 1 :]:
            if task.submitted_code is None:
                return task
        return None

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

    def find_task(self, task_id: str, round_num: int) -> CodingTask:
        """Return the task row for a bank task and follow-up round.

        Args:
            task_id: YAML task ID.
            round_num: Follow-up round (0 = initial).

        Returns:
            The matching task row.

        Raises:
            CodingTaskNotFoundError: If no row matches the keys.
        """
        for task in self.tasks:
            if task.task_id == task_id and task.round == round_num:
                return task
        raise CodingTaskNotFoundError(self.interview_id, task_id, round_num)


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
