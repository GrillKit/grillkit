# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared base aggregate for theory and coding sections."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, Protocol, Self, TypeVar


class _TaskLike(Protocol):
    """Protocol for task rows consumed by ``Section``."""

    @property
    def id(self) -> int: ...

    @property
    def round(self) -> int: ...

    @property
    def score(self) -> int | None: ...

    @property
    def started_at(self) -> datetime | None: ...


TTask = TypeVar("TTask", bound=_TaskLike)


class Section[TTask: _TaskLike](ABC):
    """Base aggregate for theory and coding sections.

    Encapsulates the ~12 identical methods that were previously duplicated
    between ``TheorySection`` and ``CodingSection``.

    Concrete subclasses MUST provide (via ``@dataclass`` fields or class vars):
    - ``status`` — section status literal (``str``)
    - ``tasks`` — ordered task rows (``tuple[TTask, ...]``)
    - ``task_time_limit_seconds`` — per-task time limit (``int | None``)
    - ``interview_id`` — parent interview UUID (``str``)
    - ``section_feedback`` — cached section evaluation (``dict[str, object] | None``)
    - ``section_score`` — cached aggregated score (``int | None``)
    - ``MAX_SCORE_PER_ROUND`` — max points per round (``int``)
    """

    # ------------------------------------------------------------------
    # Abstract hooks expected from concrete subclasses
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def MAX_SCORE_PER_ROUND(self) -> int:  # noqa: N802
        """Maximum points achievable per round."""

    @property
    @abstractmethod
    def _completion_field_name(self) -> str:
        """Attribute name that indicates a task is done (e.g. ``answer_text``)."""

    @property
    @abstractmethod
    def _task_id_field(self) -> str:
        """Attribute name that holds the bank task/question ID."""

    @abstractmethod
    def _task_not_found_error(self, task_id: str, round_num: int) -> Exception:
        """Build the domain-specific exception for a missing task."""

    @abstractmethod
    def _timeout_replacement_fields(self, task: TTask, feedback: str) -> dict[str, Any]:
        """Return the ``replace()`` kwargs for a timed-out task."""

    @abstractmethod
    def _create_follow_up(
        self,
        base: TTask,
        next_round: int,
        prompt_text: str,
        **kwargs: Any,
    ) -> TTask:
        """Instantiate a new follow-up task row."""

    # ------------------------------------------------------------------
    # Shared behaviour — relies on subclass attributes listed above
    # ------------------------------------------------------------------
    def with_activated(self: Self) -> Self:
        """Promote ``pending`` status to ``active``.

        Returns:
            Updated aggregate when status was ``pending``, otherwise ``self``.
        """
        if self.status != "pending":  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            return self
        return replace(self, status="active")  # type: ignore[type-var]  # pyright: ignore[reportArgumentType]

    def find_first_pending(self) -> TTask | None:
        """Return the first task whose completion field is still ``None``."""
        for task in self.tasks:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            if getattr(task, self._completion_field_name) is None:
                return task  # type: ignore[no-any-return]
        return None

    def is_complete(self) -> bool:
        """Return whether every task in this section has been completed."""
        return bool(self.tasks) and self.find_first_pending() is None  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]

    def total_score(self) -> int:
        """Sum scores from all completed task rounds."""
        return sum(
            (task.score or 0)  # type: ignore[misc]
            for task in self.tasks  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            if getattr(task, self._completion_field_name) is not None
        )

    def max_score(self) -> int:
        """Compute maximum achievable score for completed rounds."""
        completed = sum(
            1  # type: ignore[misc]
            for task in self.tasks  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            if getattr(task, self._completion_field_name) is not None
        )
        return self.MAX_SCORE_PER_ROUND * completed

    def with_cached_section_feedback(
        self: Self,
        feedback: dict[str, object],
        *,
        section_score: int,
    ) -> Self:
        """Return aggregate with prefetched section feedback when not cached."""
        if self.section_feedback is not None:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            return self
        return replace(  # type: ignore[type-var]
            self,  # pyright: ignore[reportArgumentType]
            section_feedback=feedback,
            section_score=section_score,
        )

    def start_timer_for_task(
        self: Self, task_row_id: int, when: datetime | None = None
    ) -> Self:
        """Start the per-task timer on a task when the section has a limit."""
        if self.task_time_limit_seconds is None:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            return self
        started_at = when or datetime.now(UTC)
        tasks = tuple(
            replace(task, started_at=started_at)
            if task.id == task_row_id and task.started_at is None
            else task
            for task in self.tasks  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
        )
        return replace(self, tasks=tasks)  # type: ignore[type-var]  # pyright: ignore[reportArgumentType]

    def with_evaluation(
        self: Self,
        task_id: str,
        round_num: int,
        score: int,
        feedback: str,
    ) -> Self:
        """Return aggregate with AI score and feedback on one task round."""
        target = self.find_task(task_id, round_num)
        tasks = tuple(
            replace(task, score=score, feedback=feedback)
            if task.id == target.id
            else task
            for task in self.tasks  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
        )
        return replace(self, tasks=tasks)  # type: ignore[type-var]  # pyright: ignore[reportArgumentType]

    def max_round_for_task(self, task_id: str) -> int:
        """Return the highest follow-up round number for a bank task ID."""
        rounds = [
            task.round
            for task in self.tasks  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            if getattr(task, self._task_id_field) == task_id
        ]
        return max(rounds) if rounds else 0

    def with_follow_up(
        self: Self,
        task_id: str,
        prompt_text: str,
        **kwargs: Any,
    ) -> tuple[Self, TTask]:
        """Return aggregate with a new pending follow-up task row."""
        base = self.find_task(task_id, 0)
        next_round = self.max_round_for_task(task_id) + 1
        follow_up = self._create_follow_up(base, next_round, prompt_text, **kwargs)
        return replace(self, tasks=self.tasks + (follow_up,)), follow_up  # type: ignore[attr-defined,type-var]  # pyright: ignore[reportAttributeAccessIssue,reportArgumentType]

    def find_next_pending_after(self, current_index: int) -> TTask | None:
        """Return the next pending task after a position in the task list."""
        for task in self.tasks[current_index + 1 :]:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            if getattr(task, self._completion_field_name) is None:
                return task  # type: ignore[no-any-return]
        return None

    def find_task(self, task_id: str, round_num: int) -> TTask:
        """Return the task row for a bank task and follow-up round.

        Raises:
            Exception: Domain-specific ``*TaskNotFoundError`` when no row matches.
        """
        for task in self.tasks:  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
            if (
                getattr(task, self._task_id_field) == task_id
                and task.round == round_num
            ):
                return task  # type: ignore[no-any-return]
        raise self._task_not_found_error(task_id, round_num)

    def with_timed_out_round(self: Self, task_row_id: int, feedback: str) -> Self:
        """Return aggregate with a task round marked as timed out."""
        tasks = tuple(
            replace(task, **self._timeout_replacement_fields(task, feedback))
            if task.id == task_row_id
            else task
            for task in self.tasks  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
        )
        return replace(self, tasks=tasks)  # type: ignore[type-var]  # pyright: ignore[reportArgumentType]
