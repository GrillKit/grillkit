# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""AI-only evaluation for submitted interview answers."""

from app.ai.base import AIProvider
from app.interview.services.evaluator.service import (
    AnswerEvaluation,
    FollowUpEvaluation,
    InterviewEvaluatorService,
)


class AnswerAiEvaluationService:
    """Run LLM evaluation and decide whether a follow-up is needed."""

    @staticmethod
    async def evaluate(
        *,
        question_id: str,
        answer_round: int,
        question_text: str,
        question_code: str | None,
        answer_text: str,
        initial_question_text: str,
        initial_answer_text: str,
        provider: AIProvider,
        locale: str,
    ) -> tuple[AnswerEvaluation | FollowUpEvaluation, bool, str | None]:
        """Run AI evaluation and decide follow-up.

        Args:
            question_id: Question ID from the answer row.
            answer_round: Follow-up round (0 = initial).
            question_text: Text of the question being answered.
            question_code: Optional code snippet for the question.
            answer_text: The user's answer text.
            initial_question_text: Original question text (round 0).
            initial_answer_text: User's initial answer text (round 0).
            provider: Configured AI provider.
            locale: Locale for AI feedback and follow-up questions.

        Returns:
            Tuple of (evaluation, follow_up_needed, follow_up_text).
        """
        evaluation: AnswerEvaluation | FollowUpEvaluation
        if answer_round == 0:
            evaluation = await InterviewEvaluatorService.evaluate_answer(
                provider=provider,
                question_text=question_text,
                answer_text=answer_text,
                question_code=question_code,
                locale=locale,
            )
            follow_up_needed = evaluation.follow_up_needed and bool(
                evaluation.follow_up_question
            )
            follow_up_text = evaluation.follow_up_question
        else:
            evaluation = await InterviewEvaluatorService.evaluate_follow_up(
                provider=provider,
                question_text=initial_question_text,
                initial_answer=initial_answer_text,
                follow_up_question=question_text,
                follow_up_answer=answer_text,
                question_code=question_code,
                locale=locale,
            )
            follow_up_needed = (
                evaluation.needs_further_follow_up
                and bool(evaluation.follow_up_question)
                and answer_round < InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH
            )
            follow_up_text = evaluation.follow_up_question

        return evaluation, follow_up_needed, follow_up_text
