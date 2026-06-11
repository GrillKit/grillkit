# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Merge per-section evaluation summaries for session completion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.interview.services.sections import SectionEvaluationSummary
from app.shared.evaluation_models import InterviewEvaluation


@dataclass(frozen=True, slots=True)
class MergedSessionEvaluation:
    """Combined evaluation inputs from all enabled interview sections.

    Attributes:
        sections: Non-empty section summaries in phase order.
    """

    sections: tuple[SectionEvaluationSummary, ...]

    @property
    def all_items(self) -> tuple[dict[str, Any], ...]:
        """Return Q&A items from every section in order."""
        rows: list[dict[str, Any]] = []
        for section in self.sections:
            rows.extend(section.items)
        return tuple(rows)

    def has_cached_narratives(self) -> bool:
        """Return whether every non-skipped section has cached narrative feedback."""
        actionable = [section for section in self.sections if not section.skipped]
        if not actionable:
            return False
        return all(section.cached_narrative is not None for section in actionable)

    def to_score_breakdown(self) -> dict[str, Any]:
        """Build nested score breakdown keyed by section kind.

        Returns:
            Mapping ``theory`` / ``coding`` to score metadata and per-question rows.
        """
        breakdown: dict[str, Any] = {}
        for section in self.sections:
            question_rows: dict[str, Any] = {}
            for item in section.items:
                item_id = item.get("question_id") or item.get("task_id") or "?"
                question_id = str(item_id)
                round_num = int(item.get("round", 0))
                key = question_id if round_num == 0 else f"{question_id}:r{round_num}"
                score = item.get("score")
                question_rows[key] = {
                    "score": score if isinstance(score, int) else 0,
                    "max": 5,
                }
            breakdown[section.section] = {
                "score": section.score,
                "max": section.max_score,
                "skipped": section.skipped,
                "questions": question_rows,
            }
        return breakdown


def attach_session_score_breakdown(
    evaluation: InterviewEvaluation,
    merged: MergedSessionEvaluation,
) -> InterviewEvaluation:
    """Attach merged section score breakdown before session persistence.

    Args:
        evaluation: Session narrative from the evaluator service.
        merged: Combined section summaries from the aggregator.

    Returns:
        Evaluation with ``score_breakdown`` populated from merged sections.
    """
    return evaluation.model_copy(
        update={"score_breakdown": merged.to_score_breakdown()}
    )


class SessionEvaluationAggregator:
    """Merge section evaluation summaries for session-level completion."""

    @staticmethod
    def merge(
        *summaries: SectionEvaluationSummary | None,
    ) -> MergedSessionEvaluation:
        """Combine section summaries, ignoring ``None`` placeholders.

        Args:
            *summaries: Section summaries in phase order (``None`` when disabled).

        Returns:
            Merged evaluation payload for session completion.

        Raises:
            ValueError: If no section summaries are provided.
        """
        present = tuple(summary for summary in summaries if summary is not None)
        if not present:
            raise ValueError("At least one section summary is required")
        return MergedSessionEvaluation(sections=present)

    @staticmethod
    def total_score_from_breakdown(score_breakdown: dict[str, Any] | None) -> int:
        """Sum earned points across nested section breakdown entries.

        Args:
            score_breakdown: Nested breakdown from ``to_score_breakdown``.

        Returns:
            Total earned score across all sections.
        """
        if not score_breakdown:
            return 0
        total = 0
        for key, section in score_breakdown.items():
            if key == "total" or not isinstance(section, dict):
                continue
            score = section.get("score")
            if isinstance(score, int):
                total += score
        return total
