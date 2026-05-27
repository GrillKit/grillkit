# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""AI-powered interview evaluation service."""

from typing import Any

from app.ai.base import AIProvider, Message
from app.interview.services.evaluator.models import (
    AnswerEvaluation,
    FollowUpEvaluation,
    InterviewEvaluation,
)
from app.interview.services.evaluator.prompts import (
    ANSWER_EVALUATION_INSTRUCTIONS,
    FOLLOW_UP_EVALUATION_INSTRUCTIONS,
    SESSION_EVALUATION_INSTRUCTIONS,
    build_evaluator_instructions,
    build_prompt_with_schema,
    looks_like_json_schema_fragment,
    parse_json_response,
)
from app.shared.locales import DEFAULT_LOCALE

__all__ = [
    "AnswerEvaluation",
    "FollowUpEvaluation",
    "InterviewEvaluation",
    "InterviewEvaluatorService",
    "looks_like_json_schema_fragment",
]


class InterviewEvaluatorService:
    """Service for AI-powered evaluation of interview answers.

    Uses the configured AI provider to evaluate answers, generate follow-up
    questions, and produce final session evaluations.
    """

    MAX_FOLLOW_UP_DEPTH = 2

    @staticmethod
    async def evaluate_answer(
        provider: AIProvider,
        question_text: str,
        answer_text: str,
        question_code: str | None = None,
        locale: str = DEFAULT_LOCALE,
    ) -> AnswerEvaluation:
        """Evaluate a user's initial answer (round=0).

        Args:
            provider: Configured AI provider instance.
            question_text: The question text.
            answer_text: The user's answer.
            question_code: Optional code snippet from the question.
            locale: Locale for AI feedback and follow-up questions.

        Returns:
            AnswerEvaluation with score, feedback, and follow-up decision.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        question = question_text
        if question_code:
            question += f"\n\nCode:\n{question_code}"

        instructions = build_evaluator_instructions(
            locale, ANSWER_EVALUATION_INSTRUCTIONS
        )
        system_prompt = build_prompt_with_schema(instructions, AnswerEvaluation)

        messages = [
            Message(role="system", content=system_prompt),
            Message(
                role="user",
                content=f"Question:\n{question}\n\nAnswer:\n{answer_text}",
            ),
        ]

        result = await provider.generate(
            messages=messages, temperature=0.3, max_tokens=1000
        )

        return parse_json_response(result.content, AnswerEvaluation)

    @staticmethod
    async def evaluate_follow_up(
        provider: AIProvider,
        question_text: str,
        initial_answer: str,
        follow_up_question: str,
        follow_up_answer: str,
        question_code: str | None = None,
        locale: str = DEFAULT_LOCALE,
    ) -> FollowUpEvaluation:
        """Evaluate a user's follow-up answer (round >= 1).

        Args:
            provider: Configured AI provider instance.
            question_text: The original question text.
            initial_answer: The user's initial answer.
            follow_up_question: The follow-up question text.
            follow_up_answer: The user's follow-up answer.
            question_code: Optional code snippet from the question.
            locale: Locale for AI feedback and follow-up questions.

        Returns:
            FollowUpEvaluation with score and further follow-up decision.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        question = question_text
        if question_code:
            question += f"\n\nCode:\n{question_code}"

        instructions = build_evaluator_instructions(
            locale, FOLLOW_UP_EVALUATION_INSTRUCTIONS
        )
        system_prompt = build_prompt_with_schema(instructions, FollowUpEvaluation)

        messages = [
            Message(role="system", content=system_prompt),
            Message(
                role="user",
                content=(
                    f"Original Question:\n{question}\n\n"
                    f"Initial Answer:\n{initial_answer}\n\n"
                    f"Follow-up Question:\n{follow_up_question}\n\n"
                    f"Follow-up Answer:\n{follow_up_answer}"
                ),
            ),
        ]

        result = await provider.generate(
            messages=messages, temperature=0.3, max_tokens=1000
        )

        return parse_json_response(result.content, FollowUpEvaluation)

    @staticmethod
    async def evaluate_interview(
        provider: AIProvider,
        questions_answers: list[dict[str, Any]],
        sources_text: str,
        locale: str = DEFAULT_LOCALE,
    ) -> InterviewEvaluation:
        """Provide a final evaluation of an entire interview session.

        Args:
            provider: Configured AI provider instance.
            questions_answers: List of dicts with question_id, question_text,
                answer_text, score, round for each answer.
            sources_text: Human-readable list of tracks, levels, and topics.
            locale: Locale for the final evaluation narrative.

        Returns:
            InterviewEvaluation with overall feedback and recommendations.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        qa_summary: list[str] = []
        for qa in questions_answers:
            qa_id = qa.get("question_id", "?")
            qa_round = qa.get("round", 0)
            q_text = qa.get("question_text", "")
            a_text = qa.get("answer_text", "(skipped)")
            score = qa.get("score", "N/A")
            qa_summary.append(
                f"Question {qa_id} (round {qa_round}):\n"
                f"Q: {q_text}\n"
                f"A: {a_text}\n"
                f"Score: {score}"
            )

        summary_text = "\n\n".join(qa_summary)

        instructions = build_evaluator_instructions(
            locale, SESSION_EVALUATION_INSTRUCTIONS
        )
        system_prompt = build_prompt_with_schema(instructions, InterviewEvaluation)

        messages = [
            Message(role="system", content=system_prompt),
            Message(
                role="user",
                content=(
                    f"Sources:\n{sources_text}\n\n"
                    f"Questions and Answers:\n{summary_text}"
                ),
            ),
        ]

        result = await provider.generate(
            messages=messages, temperature=0.3, max_tokens=1500
        )

        return parse_json_response(result.content, InterviewEvaluation)
