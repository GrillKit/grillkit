# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section review page context builder."""

from __future__ import annotations

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.section_review_support import (
    CompletedInterviewSnapshot,
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

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this review scope.
        """
        self._uow = uow
        self._query = TheoryQueryService(uow)

    def build_context(
        self,
        interview_id: str,
        snapshot: CompletedInterviewSnapshot,
    ) -> TheoryReviewContext | None:
        """Assemble theory review template context for a completed session.

        Args:
            interview_id: Parent session UUID.
            snapshot: Loaded completed interview snapshot.

        Returns:
            Review context, or None when the theory section is missing.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            return None

        summary = self._query.get_evaluation_summary(interview_id)
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

    def build_context_for(self, interview_id: str) -> TheoryReviewContext | None:
        """Build theory review context for a completed session.

        Args:
            interview_id: Parent session UUID.

        Returns:
            Review context, or None when the session or theory section is missing.
        """
        snapshot = load_completed_interview(self._uow, interview_id)
        if snapshot is None:
            return None
        return self.build_context(interview_id, snapshot)
