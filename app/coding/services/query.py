# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section read-only query helpers."""

from typing import Any

from app.coding.domain.entities import CodingSection
from app.coding.repositories.uow import CodingUnitOfWork
from app.interview.services.rules.selection import selection_sources_summary
from app.interview.services.section_evaluation import build_section_evaluation_summary
from app.interview.services.sections import SectionEvaluationSummary


class CodingQueryService:
    """Read-only queries for coding section aggregates."""

    @staticmethod
    def _items_from_section(section: CodingSection) -> tuple[dict[str, Any], ...]:
        """Build task rows from a coding section aggregate.

        Args:
            section: Domain coding section with tasks loaded.

        Returns:
            Tuple of dicts with task and submission fields for evaluation.
        """
        return tuple(
            {
                "task_id": task.task_id,
                "prompt_text": task.prompt_text,
                "submitted_code": task.submitted_code,
                "score": task.score,
                "round": task.round,
                "feedback": task.feedback,
            }
            for task in section.tasks
            if task.submitted_code is not None
        )

    @staticmethod
    def get_evaluation_summary(interview_id: str) -> SectionEvaluationSummary | None:
        """Return coding section evaluation data for session completion.

        Uses cached ``section_feedback`` when present.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Section summary, or None when no coding section exists.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return None

            return build_section_evaluation_summary(
                "coding",
                section_status=section.status,
                items=CodingQueryService._items_from_section(section),
                total_score=section.total_score(),
                max_score=section.max_score(),
                cached_narrative=section.section_feedback,
            )

    @staticmethod
    def sources_text_for_section(interview_id: str) -> str:
        """Build selection summary text for coding evaluation prompts.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Human-readable selection summary, or empty string when missing.
        """
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                return ""
            return selection_sources_summary(section.selection)
