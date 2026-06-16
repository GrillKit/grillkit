# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section read-only query helpers."""

from typing import Any

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.rules.selection import selection_sources_summary
from app.interview.services.section_evaluation import build_section_evaluation_summary
from app.interview.services.sections import SectionEvaluationSummary
from app.theory.domain.entities import TheorySection


class TheoryQueryService:
    """Read-only queries for theory section aggregates."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this read scope.
        """
        self._uow = uow

    @staticmethod
    def _qa_items_from_section(
        section: TheorySection,
    ) -> tuple[dict[str, Any], ...]:
        """Build Q&A rows from a theory section aggregate.

        Args:
            section: Domain theory section with tasks loaded.

        Returns:
            Tuple of dicts with question and answer fields for evaluation.
        """
        return tuple(
            {
                "question_id": task.question_id,
                "question_text": task.question_text,
                "answer_text": task.answer_text,
                "score": task.score,
                "round": task.round,
                "feedback": task.feedback,
            }
            for task in section.tasks
            if task.answer_text is not None
        )

    def get_evaluation_summary(
        self,
        interview_id: str,
    ) -> SectionEvaluationSummary | None:
        """Return theory section evaluation data for session completion.

        Uses cached ``section_feedback`` when present.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section summary, or None when no theory section exists.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            return None

        return build_section_evaluation_summary(
            "theory",
            section_status=section.status,
            items=self._qa_items_from_section(section),
            total_score=section.total_score(),
            max_score=section.max_score(),
            cached_narrative=section.section_feedback,
        )

    def sources_text_for_section(self, interview_id: str) -> str:
        """Build selection summary text for theory evaluation prompts.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Human-readable selection summary, or empty string when missing.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            return ""
        return selection_sources_summary(section.selection)
