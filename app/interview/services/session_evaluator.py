# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session-level evaluation built from merged section summaries."""

import logging
from typing import Any

from app.ai.base import AIProvider
from app.interview.services.evaluation_aggregator import MergedSessionEvaluation
from app.interview.services.sections import SectionEvaluationSummary
from app.shared.evaluation_models import InterviewEvaluation
from app.theory.services.evaluator.service import TheoryEvaluatorService

logger = logging.getLogger(__name__)


class SessionEvaluatorService:
    """Produce the final session evaluation narrative."""

    @staticmethod
    def _normalize_item_for_session_eval(item: dict[str, Any]) -> dict[str, Any]:
        """Map coding task rows to the theory session-evaluator field names.

        Args:
            item: Theory Q&A row or coding task submission row.

        Returns:
            Dict with ``question_id``, ``question_text``, ``answer_text``, ``score``,
            and ``round`` keys for prompt formatting.
        """
        if "question_id" in item:
            return item
        if "task_id" in item:
            normalized = {
                "question_id": item["task_id"],
                "question_text": item.get("prompt_text", ""),
                "answer_text": item.get("submitted_code", "(skipped)"),
                "score": item.get("score", "N/A"),
                "round": item.get("round", 0),
            }
            feedback = item.get("feedback")
            if feedback is not None:
                normalized["feedback"] = feedback
            return normalized
        return item

    @staticmethod
    def _build_from_cached_narratives(
        merged: MergedSessionEvaluation,
    ) -> InterviewEvaluation:
        """Build a session evaluation from prefetched section narratives.

        Args:
            merged: Combined section summaries with cached narratives.

        Returns:
            Session evaluation narrative without ``score_breakdown``.
        """
        feedback_parts: list[str] = []
        topics: list[str] = []
        strengths: list[str] = []

        for section in merged.sections:
            if section.skipped:
                continue
            SessionEvaluatorService._collect_section_narrative(
                section,
                feedback_parts=feedback_parts,
                topics=topics,
                strengths=strengths,
            )

        overall_feedback = " ".join(
            part for part in feedback_parts if part.strip()
        ).strip()
        if not overall_feedback:
            overall_feedback = "Session evaluation complete."

        return InterviewEvaluation(
            overall_feedback=overall_feedback,
            topics_to_review=topics,
            strengths_summary=strengths,
            score_breakdown={},
        )

    @staticmethod
    def _append_unique_strings(target: list[str], values: object) -> None:
        """Append string values to a list when not already present.

        Args:
            target: Destination list of unique strings.
            values: Iterable or scalar value from a narrative payload.
        """
        if isinstance(values, str):
            if values and values not in target:
                target.append(values)
            return
        if not isinstance(values, list):
            return
        for value in values:
            if isinstance(value, str) and value and value not in target:
                target.append(value)

    @staticmethod
    def _synthesize_from_merged(
        merged: MergedSessionEvaluation,
    ) -> InterviewEvaluation:
        """Build a session evaluation without calling the LLM.

        Args:
            merged: Combined section summaries from the aggregator.

        Returns:
            Synthesized session evaluation using per-task feedback when available.
        """
        feedback_parts: list[str] = []
        topics: list[str] = []
        strengths: list[str] = []

        for section in merged.sections:
            if section.skipped:
                feedback_parts.append(
                    f"The {section.section} section was not completed."
                )
                continue

            SessionEvaluatorService._collect_section_narrative(
                section,
                feedback_parts=feedback_parts,
                topics=topics,
                strengths=strengths,
            )
            SessionEvaluatorService._collect_item_feedback(section, feedback_parts)

        overall_feedback = "\n\n".join(
            part for part in feedback_parts if part.strip()
        ).strip()
        if not overall_feedback:
            overall_feedback = "Session evaluation complete."

        return InterviewEvaluation(
            overall_feedback=overall_feedback,
            topics_to_review=topics,
            strengths_summary=strengths,
            score_breakdown={},
        )

    @staticmethod
    def _collect_section_narrative(
        section: SectionEvaluationSummary,
        *,
        feedback_parts: list[str],
        topics: list[str],
        strengths: list[str],
    ) -> None:
        """Merge cached section narrative fields into synthesis buffers.

        Args:
            section: Section summary with optional cached narrative.
            feedback_parts: Overall feedback fragments to append to.
            topics: Topic list to extend uniquely.
            strengths: Strength list to extend uniquely.
        """
        if section.cached_narrative is None:
            return
        narrative = section.cached_narrative
        section_feedback = str(narrative.get("section_feedback", "")).strip()
        if section_feedback:
            feedback_parts.append(section_feedback)
        SessionEvaluatorService._append_unique_strings(
            topics, narrative.get("topics_to_review", [])
        )
        SessionEvaluatorService._append_unique_strings(
            strengths, narrative.get("strengths_summary", [])
        )

    @staticmethod
    def _collect_item_feedback(
        section: SectionEvaluationSummary,
        feedback_parts: list[str],
    ) -> None:
        """Append per-task feedback rows when no section narrative exists.

        Args:
            section: Section summary with evaluated task rows.
            feedback_parts: Overall feedback fragments to append to.
        """
        if section.cached_narrative is not None:
            return
        for item in section.items:
            feedback = item.get("feedback")
            if isinstance(feedback, str) and feedback.strip():
                feedback_parts.append(feedback.strip())

    @staticmethod
    async def evaluate_session(
        merged: MergedSessionEvaluation,
        *,
        provider: AIProvider,
        locale: str,
        sources_text: str,
    ) -> InterviewEvaluation:
        """Evaluate a session from merged section summaries.

        Reuses cached section narratives when every actionable section has
        prefetched feedback; otherwise calls the LLM once with all Q&A rows.
        Falls back to synthesized feedback when the LLM returns invalid output.

        Score breakdown is attached later by ``attach_session_score_breakdown``
        in the completion service before persistence.

        Args:
            merged: Combined section summaries from the aggregator.
            provider: AI provider for final evaluation.
            locale: Locale for the session narrative.
            sources_text: Human-readable selection summary for prompts.

        Returns:
            Session evaluation narrative without ``score_breakdown``.
        """
        if merged.has_cached_narratives():
            return SessionEvaluatorService._build_from_cached_narratives(merged)

        normalized_items = [
            SessionEvaluatorService._normalize_item_for_session_eval(item)
            for item in merged.all_items
        ]
        try:
            interview_eval = await TheoryEvaluatorService.evaluate_interview(
                provider=provider,
                questions_answers=normalized_items,
                sources_text=sources_text,
                locale=locale,
            )
            if not interview_eval.overall_feedback.strip():
                raise ValueError("AI returned empty evaluation")
            return interview_eval.model_copy(update={"score_breakdown": {}})
        except Exception as exc:
            logger.warning(
                "Session LLM evaluation failed; using synthesized feedback: %s",
                exc,
            )
            return SessionEvaluatorService._synthesize_from_merged(merged)
