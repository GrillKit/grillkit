# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview creation service."""

import json
import logging
import random
from uuid import uuid4

from app.questions import load_category
from app.shared.domain.locales import normalize_locale
from app.shared.infrastructure.models import Answer, Interview
from app.shared.infrastructure.uow import UnitOfWork

logger = logging.getLogger(__name__)


class InterviewCreationService:
    """Service for creating interview sessions."""

    @staticmethod
    def create_interview(
        level: str,
        category: str,
        language: str = "python",
        locale: str = "en",
        question_count: int = 5,
    ) -> Interview:
        """Create a new interview session with selected questions.

        Loads questions from YAML bank, shuffles and picks the requested
        number, then persists the session to the database atomically.

        Args:
            level: Difficulty level (junior, middle, senior).
            category: Question category name.
            language: Programming language (default: "python").
            locale: Language for AI feedback and follow-ups (default: "en").
            question_count: Number of questions for this session (default: 5).

        Returns:
            The created Interview instance with answers pre-populated.

        Raises:
            ValueError: If no questions found for the given criteria.
        """
        locale = normalize_locale(locale)
        questions = load_category(language, level, category)
        if not questions:
            raise ValueError(f"No questions found for {language}/{level}/{category}")

        random.shuffle(questions)
        selected = questions[:question_count]
        question_ids = [q.id for q in selected]
        interview_id = str(uuid4())

        with UnitOfWork(auto_commit=True) as uow:
            interview = Interview(
                id=interview_id,
                level=level,
                language=language,
                locale=locale,
                category=category,
                question_count=len(selected),
                question_ids=json.dumps(question_ids),
                status="active",
            )
            uow.interviews.add(interview)

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

            uow.flush()
            uow.session.refresh(interview)
            uow.session.expunge(interview)
            return interview
