# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview creation service."""

import logging
from uuid import uuid4

from app.interview.domain.entities import Interview
from app.interview.domain.value_objects import InterviewSelection
from app.interview.repositories.mappers import interview_to_read
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.services.question_planning import build_question_plan
from app.interview.services.rules.selection import validate_question_count
from app.shared.locales import normalize_locale

logger = logging.getLogger(__name__)


class InterviewCreationService:
    """Service for creating interview sessions."""

    @staticmethod
    def create_interview(
        selection: InterviewSelection,
        locale: str = "en",
        question_count: int = 5,
        question_time_limit_seconds: int | None = None,
    ) -> InterviewRead:
        """Create a new interview session with selected questions.

        Loads questions from YAML banks per selection, builds a plan with at
        least one question per topic, then persists the session atomically.

        Args:
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback and follow-ups (default: "en").
            question_count: Number of questions for this session (default: 5).
            question_time_limit_seconds: Per-round time limit, or None to disable.

        Returns:
            Read model for the created interview with answers pre-populated.

        Raises:
            ValueError: If validation fails or no questions are available.
        """
        locale = normalize_locale(locale)
        validate_question_count(selection, question_count)
        selected = build_question_plan(selection, question_count, locale=locale)
        interview_id = str(uuid4())
        aggregate = Interview.start(
            interview_id,
            selection=selection,
            locale=locale,
            planned_questions=tuple(selected),
            question_time_limit_seconds=question_time_limit_seconds,
        )

        with InterviewUnitOfWork(auto_commit=True) as uow:
            persisted = uow.interviews.create_aggregate(aggregate)
            return interview_to_read(persisted)
