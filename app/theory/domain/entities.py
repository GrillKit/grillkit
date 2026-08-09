# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section aggregate entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal

from app.interview.domain.value_objects import InterviewSelection
from app.shared.section import Section
from app.shared.timed_task import TimedTask
from app.theory.domain.exceptions import (
    TheorySectionNotActiveError,
    TheoryTaskNotFoundError,
    UnansweredTaskNotFoundError,
)
from app.theory.domain.value_objects import PlannedTheoryQuestion

TheorySectionStatus = Literal["active", "completed", "skipped"]


@dataclass(frozen=True, slots=True)
class TheoryTask(TimedTask):
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


@dataclass(frozen=True, slots=True)
class TheorySection(Section[TheoryTask]):
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

    MAX_SCORE_PER_ROUND = 5  # pyright: ignore
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

    # ------------------------------------------------------------------
    # Section abstract hooks
    # ------------------------------------------------------------------
    @property
    def _completion_field_name(self) -> str:
        return "answer_text"

    @property
    def _task_id_field(self) -> str:
        return "question_id"

    def _task_not_found_error(self, task_id: str, round_num: int) -> Exception:
        return TheoryTaskNotFoundError(self.interview_id, task_id, round_num)

    def _timeout_replacement_fields(
        self, task: TheoryTask, feedback: str
    ) -> dict[str, Any]:
        return {
            "answer_text": TheoryTask.TIME_EXPIRED_ANSWER_TEXT,
            "score": 0,
            "feedback": feedback,
        }

    def _create_follow_up(
        self,
        base: TheoryTask,
        next_round: int,
        prompt_text: str,
        **kwargs: Any,
    ) -> TheoryTask:
        return TheoryTask(
            id=TheoryTask.NEW_ID,
            theory_section_id=self.id,
            interview_id=self.interview_id,
            question_id=base.question_id,
            order=base.order,
            round=next_round,
            question_text=prompt_text,
            question_code=base.question_code,
            answer_text=None,
            score=None,
            feedback=None,
            started_at=None,
            created_at=datetime.now(UTC),
            expected_points=base.expected_points,
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

    # ------------------------------------------------------------------
    # Domain-specific behaviour
    # ------------------------------------------------------------------
    def ensure_active(self) -> None:
        """Ensure this theory section accepts new task submissions.

        Raises:
            TheorySectionNotActiveError: If the section is not in ``active`` status.
        """
        if self.status != "active":
            raise TheorySectionNotActiveError(self.interview_id)

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
