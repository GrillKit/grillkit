# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding AI evaluator service."""

from __future__ import annotations

from typing import Any, TypeVar, cast

from pydantic import BaseModel

from app.ai.base import AIProvider
from app.coding.services.evaluator.models import (
    CodingAnswerEvaluation,
    CodingFollowUpEvaluation,
)
from app.coding.services.evaluator.prompts import (
    CODING_ANSWER_EVALUATION_INSTRUCTIONS,
    CODING_FOLLOW_UP_EVALUATION_INSTRUCTIONS,
    CODING_SECTION_EVALUATION_INSTRUCTIONS,
    build_coding_evaluation_user_text,
)
from app.shared.evaluation_models import SectionEvaluation
from app.shared.structured_evaluation import evaluate_with_schema

T = TypeVar("T", bound=BaseModel)


class CodingEvaluatorService:
    """Evaluate coding submissions with run history and hidden test context."""

    MAX_FOLLOW_UP_DEPTH = 2

    @staticmethod
    async def _evaluate_with_schema(
        provider: AIProvider,
        *,
        locale: str,
        instructions: str,
        response_model: type[T],
        user_text: str,
        max_tokens: int = 1200,
    ) -> T:
        """Run a structured coding evaluation via the configured provider.

        Args:
            provider: Configured AI provider instance.
            locale: Locale for AI feedback.
            instructions: Evaluator instruction template constant.
            response_model: Pydantic model for parsed JSON output.
            user_text: User message with task and submission context.
            max_tokens: Maximum tokens for the model response.

        Returns:
            Parsed evaluation model instance.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        return await evaluate_with_schema(
            provider,
            locale=locale,
            instructions=instructions,
            response_model=response_model,
            user_text=user_text,
            max_tokens=max_tokens,
        )

    @staticmethod
    def _expected_points(task_spec: dict[str, Any]) -> list[str]:
        """Extract rubric bullets from a persisted task spec.

        Args:
            task_spec: Task metadata JSON.

        Returns:
            List of expected rubric point strings.
        """
        raw_points = task_spec.get("expected_points")
        if not isinstance(raw_points, list):
            return []
        return [str(point) for point in raw_points]

    @staticmethod
    def _follow_up_decision(
        evaluation: CodingAnswerEvaluation | CodingFollowUpEvaluation,
        answer_round: int,
    ) -> tuple[bool, str | None, str | None]:
        """Decide whether another follow-up round is needed.

        Args:
            evaluation: Parsed AI evaluation for the submitted round.
            answer_round: Follow-up round that was evaluated (0 = initial).

        Returns:
            Tuple of follow_up_needed, follow_up_text, follow_up_mode.
        """
        if answer_round == 0:
            if not isinstance(evaluation, CodingAnswerEvaluation):
                raise TypeError("Round 0 evaluation must be CodingAnswerEvaluation")
            follow_up_needed = evaluation.follow_up_needed and bool(
                evaluation.follow_up_question
            )
            mode = evaluation.follow_up_mode if follow_up_needed else None
            return follow_up_needed, evaluation.follow_up_question, mode
        if not isinstance(evaluation, CodingFollowUpEvaluation):
            raise TypeError(
                "Follow-up round evaluation must be CodingFollowUpEvaluation"
            )
        follow_up_needed = (
            evaluation.needs_further_follow_up
            and bool(evaluation.follow_up_question)
            and answer_round < CodingEvaluatorService.MAX_FOLLOW_UP_DEPTH
        )
        mode = evaluation.follow_up_mode if follow_up_needed else None
        return follow_up_needed, evaluation.follow_up_question, mode

    @staticmethod
    async def evaluate_submission(
        *,
        provider: AIProvider,
        locale: str,
        answer_round: int,
        prompt_text: str,
        task_spec: dict[str, Any],
        source_code: str,
        run_attempts: tuple[dict[str, Any], ...],
        submit_test_summary: dict[str, Any] | None,
        initial_prompt_text: str = "",
        initial_source_code: str = "",
    ) -> tuple[
        CodingAnswerEvaluation | CodingFollowUpEvaluation,
        bool,
        str | None,
        str | None,
    ]:
        """Evaluate one coding submission round and decide on follow-up.

        Args:
            provider: Configured AI provider instance.
            locale: Locale for AI feedback.
            answer_round: Follow-up round (0 = initial).
            prompt_text: Prompt for the evaluated round.
            task_spec: Persisted task metadata for the round.
            source_code: Submitted editor contents.
            run_attempts: Serialized Run attempt history for the initial task row.
            submit_test_summary: Hidden test summary from submit.
            initial_prompt_text: Original task prompt for follow-up rounds.
            initial_source_code: Initial submitted code for follow-up rounds.

        Returns:
            Tuple of evaluation, follow_up_needed, follow_up_text, follow_up_mode.
        """
        expected_points = CodingEvaluatorService._expected_points(task_spec)
        evaluation: CodingAnswerEvaluation | CodingFollowUpEvaluation
        if answer_round == 0:
            user_text = build_coding_evaluation_user_text(
                prompt_text=prompt_text,
                source_code=source_code,
                expected_points=expected_points,
                run_attempts=run_attempts,
                submit_test_summary=submit_test_summary,
            )
            evaluation = await CodingEvaluatorService._evaluate_with_schema(
                provider,
                locale=locale,
                instructions=CODING_ANSWER_EVALUATION_INSTRUCTIONS,
                response_model=CodingAnswerEvaluation,
                user_text=user_text,
            )
        else:
            user_text = build_coding_evaluation_user_text(
                prompt_text=prompt_text,
                source_code=source_code,
                expected_points=expected_points,
                run_attempts=run_attempts,
                submit_test_summary=submit_test_summary,
                initial_prompt_text=initial_prompt_text,
                initial_source_code=initial_source_code,
                follow_up_prompt=prompt_text,
            )
            evaluation = cast(
                CodingFollowUpEvaluation,
                await CodingEvaluatorService._evaluate_with_schema(
                    provider,
                    locale=locale,
                    instructions=CODING_FOLLOW_UP_EVALUATION_INSTRUCTIONS,
                    response_model=CodingFollowUpEvaluation,
                    user_text=user_text,
                ),
            )

        follow_up_needed, follow_up_text, follow_up_mode = (
            CodingEvaluatorService._follow_up_decision(evaluation, answer_round)
        )
        return evaluation, follow_up_needed, follow_up_text, follow_up_mode

    @staticmethod
    async def evaluate_section(
        provider: AIProvider,
        task_submissions: list[dict[str, Any]],
        sources_text: str,
        locale: str,
    ) -> SectionEvaluation:
        """Provide a narrative evaluation for one coding section.

        Args:
            provider: Configured AI provider instance.
            task_submissions: Per-round coding task rows for the section.
            sources_text: Human-readable list of tracks, levels, and topics.
            locale: Locale for the section evaluation narrative.

        Returns:
            SectionEvaluation with narrative feedback and recommendations.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        summary_rows: list[str] = []
        for row in task_submissions:
            task_id = row.get("task_id", "?")
            task_round = row.get("round", 0)
            prompt_text = row.get("prompt_text", "")
            submitted_code = row.get("submitted_code", "(skipped)")
            score = row.get("score", "N/A")
            summary_rows.append(
                f"Task {task_id} (round {task_round}):\n"
                f"Prompt: {prompt_text}\n"
                f"Submission: {submitted_code}\n"
                f"Score: {score}"
            )

        summary_text = "\n\n".join(summary_rows)
        user_text = (
            f"Sources:\n{sources_text}\n\n"
            f"Section Coding Tasks and Submissions:\n{summary_text}"
        )
        return await CodingEvaluatorService._evaluate_with_schema(
            provider,
            locale=locale,
            instructions=CODING_SECTION_EVALUATION_INSTRUCTIONS,
            response_model=SectionEvaluation,
            user_text=user_text,
            max_tokens=1200,
        )
