# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section review page context builder."""

from __future__ import annotations

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.section_review_support import (
    load_completed_interview,
    resolved_section_feedback,
    review_score_fields,
    shared_review_fields,
)
from app.theory.schemas.review import TheoryReviewContext
from app.theory.schemas.theory import TheoryTaskRead
from app.theory.services.query import TheoryQueryService


class TheoryReviewService:
    """Build read-only theory review context for completed sessions."""

    @staticmethod
    def build_context(interview_id: str) -> TheoryReviewContext | None:
        """Assemble theory review template context for a completed session.

        Args:
            interview_id: Parent session UUID.

        Returns:
            Review context, or None when the session or theory section is missing.
        """
        snapshot = load_completed_interview(interview_id)
        if snapshot is None:
            return None

        with InterviewUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                return None

        summary = TheoryQueryService.get_evaluation_summary(interview_id)
        if summary is None:
            return None

        section_feedback = resolved_section_feedback(
            summary,
            item_id_key="question_id",
            cached_payload=section.section_feedback,
        )
        answers = [
            TheoryTaskRead.model_validate(task)
            for task in snapshot.interview.answers
            if task.answer_text is not None
        ]
        scores = review_score_fields(
            summary,
            total_score=section.total_score(),
            max_score=section.max_score(),
        )

        return TheoryReviewContext(
            **{
                **shared_review_fields(interview_id, snapshot),
                **scores,
                "section_feedback": section_feedback,
                "answers": answers,
            }
        )
