# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview creation service."""

import json
import logging
from uuid import uuid4

from app.interview.domain.selection import (
    InterviewSelection,
    selection_to_spec,
    validate_question_count,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.question_planning import build_question_plan
from app.shared.domain.locales import normalize_locale
from app.shared.infrastructure.models import Answer, Interview

logger = logging.getLogger(__name__)


class InterviewCreationService:
    """Service for creating interview sessions."""

    @staticmethod
    def create_interview(
        selection: InterviewSelection,
        locale: str = "en",
        question_count: int = 5,
        question_time_limit_seconds: int | None = None,
    ) -> Interview:
        """Create a new interview session with selected questions.

        Loads questions from YAML banks per selection, builds a plan with at
        least one question per topic, then persists the session atomically.

        Args:
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback and follow-ups (default: "en").
            question_count: Number of questions for this session (default: 5).
            question_time_limit_seconds: Per-round time limit, or None to disable.

        Returns:
            The created Interview instance with answers pre-populated.

        Raises:
            ValueError: If validation fails or no questions are available.
        """
        locale = normalize_locale(locale)
        validate_question_count(selection, question_count)
        selected = build_question_plan(selection, question_count, locale=locale)
        if not selected:
            raise ValueError("No questions found for the selected topics")

        question_ids = [q.id for q in selected]
        interview_id = str(uuid4())

        with InterviewUnitOfWork(auto_commit=True) as uow:
            interview = Interview(
                id=interview_id,
                locale=locale,
                selection_spec=selection_to_spec(selection),
                question_count=len(selected),
                question_ids=json.dumps(question_ids),
                question_time_limit_seconds=question_time_limit_seconds,
                status="active",
            )
            uow.interviews.add(interview)

            first_answer: Answer | None = None
            for order, q in enumerate(selected, start=1):
                answer = Answer(
                    interview_id=interview_id,
                    question_id=q.id,
                    order=order,
                    round=0,
                    question_text=q.text,
                    question_code=q.code,
                )
                uow.answers.add(answer)
                if order == 1:
                    first_answer = answer

            if question_time_limit_seconds and first_answer is not None:
                uow.answers.mark_started(first_answer)

            uow.flush()
            uow.session.refresh(interview)
            uow.session.expunge(interview)
            return interview
