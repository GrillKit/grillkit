# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section creation service."""

from app.interview.domain.value_objects import InterviewSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.rules.selection import validate_question_count
from app.theory.domain.entities import TheorySection
from app.theory.services.planning import build_theory_question_plan


class TheorySectionCreationService:
    """Service for creating theory sections within an interview session."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
        """
        self._uow = uow

    def create(
        self,
        interview_id: str,
        *,
        selection: InterviewSelection,
        locale: str,
        question_count: int,
        task_time_limit_seconds: int | None,
        start_first_task_timer: bool = True,
        excluded_ids: frozenset[str] = frozenset(),
    ) -> TheorySection:
        """Plan questions and persist a theory section with initial tasks.

        Args:
            interview_id: Parent interview UUID.
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback and follow-ups.
            question_count: Number of questions for this section.
            task_time_limit_seconds: Per-round time limit, or None to disable.
            start_first_task_timer: Whether to start the timer on the first task now.
            excluded_ids: Question IDs to omit during planning.

        Returns:
            Persisted theory section aggregate with assigned task IDs.

        Raises:
            ValueError: If validation fails or no questions are available.
        """
        validate_question_count(selection, question_count)
        theory_planned = build_theory_question_plan(
            selection,
            question_count,
            locale=locale,
            excluded_ids=excluded_ids,
        )
        section = TheorySection.start(
            interview_id,
            selection=selection,
            locale=locale,
            planned_questions=theory_planned,
            task_time_limit_seconds=task_time_limit_seconds,
            start_first_task_timer=start_first_task_timer,
        )
        return self._uow.theory_sections.create_aggregate(section)
