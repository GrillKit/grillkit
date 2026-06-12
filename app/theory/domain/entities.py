# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section aggregate entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

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
from app.theory.domain.exceptions import (
    TheorySectionNotActiveError,
    TheoryTaskNotFoundError,
    UnansweredTaskNotFoundError,
)
from app.theory.domain.value_objects import PlannedTheoryQuestion

TheorySectionStatus = Literal["active", "completed", "skipped"]


@dataclass(frozen=True, slots=True)
class TheoryTask:
    """One answer round within a theory section.

    Attributes:
        id: Task row primary key.
        theory_section_id: Parent theory section ID.
        interview_id: Parent interview UUID (denormalized from the theory section).
        question_id: YAML question ID.
        order: Display order within the section (1-based).
        round: Follow-up round number (0 = initial).
        question_text: Question text shown to the user.
        question_code: Optional code snippet for the question.
        expected_points: Rubric bullets for AI evaluation.
        answer_text: User answer text, or None when unanswered.
        score: AI score for the round, or None when not evaluated.
        feedback: AI-generated feedback text, or None.
        started_at: When the round timer started, or None.
        created_at: When this task row was created.
    """

    TIME_EXPIRED_ANSWER_TEXT = "[Time expired]"
    TIMEOUT_GRACE_SECONDS = DEFAULT_TIMEOUT_GRACE_SECONDS
    NEW_ID = 0

    id: int
    theory_section_id: int
    interview_id: str
    question_id: str
    order: int
    round: int
    question_text: str
    question_code: str | None
    answer_text: str | None
    score: int | None
    feedback: str | None
    started_at: datetime | None
    created_at: datetime
    expected_points: tuple[str, ...] = ()

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
            raise ValueError("Theory task round has no started_at")
        return shared_timer_deadline(
            self.started_at,
            limit_seconds,
            label="Theory task",
        )

    def is_timer_expired(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
        *,
        grace_seconds: int = TIMEOUT_GRACE_SECONDS,
    ) -> bool:
        """Return whether the per-round timer has elapsed.

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
        """Return whether a client-sent timeout should be accepted.

        Args:
            limit_seconds: Configured limit for the section.
            now: Current time (defaults to UTC now).

        Returns:
            True when the round timer has effectively expired for the client.
        """
        if limit_seconds is None or self.started_at is None:
            return False
        rem = self.remaining_seconds(limit_seconds, now)
        return self.is_timer_expired(limit_seconds, now, grace_seconds=0) or (
            rem is not None and rem <= 0
        )


@dataclass(frozen=True, slots=True)
class TheorySection:
    MAX_SCORE_PER_ROUND = 5
    """Theory section aggregate root.

    Attributes:
        id: Theory section primary key.
        interview_id: Parent interview UUID.
        locale: Language code for feedback and voice.
        selection: Parsed question-bank selection for this section.
        question_count: Number of questions in this section.
        question_ids: Question IDs in display order.
        task_time_limit_seconds: Per-task time limit, or None when disabled.
        status: Section status (``active``, ``completed``, or ``skipped``).
        section_score: Aggregated section score when evaluated.
        section_feedback: Parsed section evaluation payload.
        tasks: Theory tasks in display order (order, then round).
    """

    NEW_ID = 0

    id: int
    interview_id: str
    locale: str
    selection: InterviewSelection
    question_count: int
    question_ids: tuple[str, ...]
    task_time_limit_seconds: int | None
    status: TheorySectionStatus
    section_score: int | None
    section_feedback: dict[str, object] | None
    tasks: tuple[TheoryTask, ...]

    @classmethod
    def start(
        cls,
        interview_id: str,
        *,
        selection: InterviewSelection,
        locale: str,
        planned_questions: tuple[PlannedTheoryQuestion, ...],
        task_time_limit_seconds: int | None = None,
        theory_section_id: int = NEW_ID,
        start_first_task_timer: bool = True,
    ) -> TheorySection:
        """Build a new active theory section from a question plan.

        Args:
            interview_id: Parent interview UUID.
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback and follow-ups.
            planned_questions: Ordered questions for this section (non-empty).
            task_time_limit_seconds: Per-task time limit, or None to disable.
            theory_section_id: Existing section ID, or ``NEW_ID`` before insert.
            start_first_task_timer: Whether to start the timer on the first task now.

        Returns:
            Active section with initial task rows (``TheoryTask.NEW_ID``).

        Raises:
            ValueError: If ``planned_questions`` is empty.
        """
        if not planned_questions:
            raise ValueError("No questions found for the selected topics")

        when = datetime.now(UTC)
        question_ids = tuple(question.id for question in planned_questions)
        timer_start = (
            when
            if task_time_limit_seconds is not None and start_first_task_timer
            else None
        )
        tasks: list[TheoryTask] = []
        for order, question in enumerate(planned_questions, start=1):
            tasks.append(
                TheoryTask(
                    id=TheoryTask.NEW_ID,
                    theory_section_id=theory_section_id,
                    interview_id=interview_id,
                    question_id=question.id,
                    order=order,
                    round=0,
                    question_text=question.text,
                    question_code=question.code,
                    answer_text=None,
                    score=None,
                    feedback=None,
                    started_at=timer_start if order == 1 else None,
                    created_at=when,
                    expected_points=question.expected_points,
                )
            )
        return cls(
            id=theory_section_id,
            interview_id=interview_id,
            locale=locale,
            selection=selection,
            question_count=len(planned_questions),
            question_ids=question_ids,
            task_time_limit_seconds=task_time_limit_seconds,
            status="active",
            section_score=None,
            section_feedback=None,
            tasks=tuple(tasks),
        )

    def ensure_active(self) -> None:
        """Ensure this theory section accepts new task submissions.

        Raises:
            TheorySectionNotActiveError: If the section is not in ``active`` status.
        """
        if self.status != "active":
            raise TheorySectionNotActiveError(self.interview_id)

    def find_first_unanswered(self) -> TheoryTask | None:
        """Return the first unanswered task in display order.

        Returns:
            The first task with ``answer_text`` unset, or None when all are answered.
        """
        for task in self.tasks:
            if task.answer_text is None:
                return task
        return None

    def is_complete(self) -> bool:
        """Return whether every task in this section has been answered.

        Returns:
            True when there is at least one task and none remain unanswered.
        """
        return bool(self.tasks) and self.find_first_unanswered() is None

    def total_score(self) -> int:
        """Sum scores from all answered task rounds in this section.

        Returns:
            Total earned points across answered rounds.
        """
        return sum(
            (task.score or 0) for task in self.tasks if task.answer_text is not None
        )

    def max_score(self) -> int:
        """Compute maximum achievable score for answered rounds in this section.

        Returns:
            Maximum possible points for rounds with user answers.
        """
        answered_rounds = sum(1 for task in self.tasks if task.answer_text is not None)
        return self.MAX_SCORE_PER_ROUND * answered_rounds

    def with_cached_section_feedback(
        self,
        feedback: dict[str, object],
        *,
        section_score: int,
    ) -> TheorySection:
        """Return aggregate with prefetched section feedback when not already cached.

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
        self, task_id: int, when: datetime | None = None
    ) -> TheorySection:
        """Start the per-round timer on a task when the section has a limit.

        Args:
            task_id: Primary key of the task row to activate.
            when: Timestamp to set (defaults to UTC now).

        Returns:
            A new aggregate with ``started_at`` set on the target task when applicable.
        """
        if self.task_time_limit_seconds is None:
            return self
        started_at = when or datetime.now(UTC)
        tasks = tuple(
            replace(task, started_at=started_at)
            if task.id == task_id and task.started_at is None
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def with_task_text(self, task_id: int, text: str) -> TheorySection:
        """Return aggregate with user answer text on the given task.

        Args:
            task_id: Primary key of the task row to update.
            text: User answer text (maybe empty before transcription).

        Returns:
            A new aggregate with ``answer_text`` set on the target task.
        """
        tasks = tuple(
            replace(task, answer_text=text) if task.id == task_id else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def with_timed_out_round(self, task_id: int, feedback: str) -> TheorySection:
        """Return aggregate with a timed-out round scored zero.

        Args:
            task_id: Primary key of the task row that expired.
            feedback: User-facing timeout feedback text.

        Returns:
            A new aggregate with timeout marker text, score 0, and feedback.
        """
        tasks = tuple(
            replace(
                task,
                answer_text=TheoryTask.TIME_EXPIRED_ANSWER_TEXT,
                score=0,
                feedback=feedback,
            )
            if task.id == task_id
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def with_evaluation(
        self, question_id: str, round_num: int, score: int, feedback: str
    ) -> TheorySection:
        """Return aggregate with AI score and feedback on one task round.

        Args:
            question_id: YAML question ID.
            round_num: Follow-up round (0 = initial).
            score: AI score for the round.
            feedback: AI feedback text.

        Returns:
            A new aggregate with evaluation fields set on the target task.
        """
        target = self.find_task(question_id, round_num)
        tasks = tuple(
            replace(task, score=score, feedback=feedback)
            if task.id == target.id
            else task
            for task in self.tasks
        )
        return replace(self, tasks=tasks)

    def max_round_for_question(self, question_id: str) -> int:
        """Return the highest follow-up round number for a question.

        Args:
            question_id: YAML question ID.

        Returns:
            Maximum ``round`` value among tasks for the question, or 0 when none exist.
        """
        rounds = [task.round for task in self.tasks if task.question_id == question_id]
        return max(rounds) if rounds else 0

    def with_follow_up(
        self, question_id: str, question_text: str
    ) -> tuple[TheorySection, TheoryTask]:
        """Return aggregate with a new unanswered follow-up task row.

        Args:
            question_id: YAML question ID for the follow-up chain.
            question_text: Follow-up question text shown to the user.

        Returns:
            Tuple of updated aggregate and the pending follow-up task (``id`` is ``NEW_ID``).
        """
        base = self.find_task(question_id, 0)
        next_round = self.max_round_for_question(question_id) + 1
        created_at = datetime.now(UTC)
        follow_up = TheoryTask(
            id=TheoryTask.NEW_ID,
            theory_section_id=self.id,
            interview_id=self.interview_id,
            question_id=question_id,
            order=base.order,
            round=next_round,
            question_text=question_text,
            question_code=base.question_code,
            answer_text=None,
            score=None,
            feedback=None,
            started_at=None,
            created_at=created_at,
            expected_points=base.expected_points,
        )
        return replace(self, tasks=self.tasks + (follow_up,)), follow_up

    def find_unanswered_for_question(self, question_id: str) -> TheoryTask:
        """Return the unanswered task row for a question (any follow-up round).

        Args:
            question_id: YAML question ID.

        Returns:
            The first unanswered task for that question.

        Raises:
            UnansweredTaskNotFoundError: If no unanswered task exists for the question.
        """
        for task in self.tasks:
            if task.question_id == question_id and task.answer_text is None:
                return task
        raise UnansweredTaskNotFoundError(self.interview_id, question_id)

    def find_task(self, question_id: str, round_num: int) -> TheoryTask:
        """Return the task row for a question and follow-up round.

        Args:
            question_id: YAML question ID.
            round_num: Follow-up round (0 = initial).

        Returns:
            The matching task row.

        Raises:
            TheoryTaskNotFoundError: If no row matches the keys.
        """
        for task in self.tasks:
            if task.question_id == question_id and task.round == round_num:
                return task
        raise TheoryTaskNotFoundError(self.interview_id, question_id, round_num)

    def find_next_unanswered_after(self, current_index: int) -> TheoryTask | None:
        """Return the next unanswered task after a position in the task list.

        Args:
            current_index: Index of the current task in ``tasks``.

        Returns:
            The next unanswered task, or None if none remain.
        """
        for task in self.tasks[current_index + 1 :]:
            if task.answer_text is None:
                return task
        return None
