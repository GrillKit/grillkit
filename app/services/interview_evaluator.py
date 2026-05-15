# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""AI-powered interview evaluation service.

This module provides Pydantic models for structured AI output and
a service class for evaluating answers, generating follow-up questions,
and producing final session evaluations.
"""

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, Field, ValidationError

from ..ai.base import AIProvider, Message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models for structured AI output
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)


class AnswerEvaluation(BaseModel):
    """Evaluation of a single initial answer (round=0).

    Attributes:
        score: Rating 1-5.
        feedback: Detailed feedback on the answer.
        strengths: Key strengths demonstrated.
        weaknesses: Areas for improvement.
        follow_up_needed: Whether a follow-up question is needed.
        follow_up_question: The follow-up question text, if needed.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    follow_up_needed: bool = Field(..., description="Whether a follow-up is needed")
    follow_up_question: str | None = Field(None, description="Follow-up question text")


class FollowUpEvaluation(BaseModel):
    """Evaluation of a follow-up answer (round >= 1).

    Attributes:
        score: Rating 1-5 for the follow-up.
        feedback: Detailed feedback.
        needs_further_follow_up: Whether another follow-up is needed.
        follow_up_question: Next follow-up question text, if needed.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    needs_further_follow_up: bool = Field(
        ..., description="Whether another follow-up is needed"
    )
    follow_up_question: str | None = Field(
        None, description="Next follow-up question text"
    )


class SessionEvaluation(BaseModel):
    """Final evaluation of an entire interview session.

    Attributes:
        overall_feedback: Comprehensive narrative feedback on the session.
        topics_to_review: Topics the candidate should study further.
        strengths_summary: Key strengths demonstrated.
        score_breakdown: Per-question score breakdown.
    """

    overall_feedback: str = Field(..., description="Comprehensive feedback")
    topics_to_review: list[str] = Field(default_factory=list)
    strengths_summary: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper: build system prompt with embedded JSON schema
# ---------------------------------------------------------------------------


def _build_prompt_with_schema(instructions: str, model_class: type[BaseModel]) -> str:
    """Build a system prompt with the Pydantic model's JSON schema embedded.

    Args:
        instructions: Natural language instructions for the AI.
        model_class: Pydantic model class whose schema to embed.

    Returns:
        Complete system prompt string.
    """
    schema = model_class.model_json_schema()
    schema_str = json.dumps(schema, indent=2)
    return (
        f"{instructions}\n\n"
        f"You MUST respond with valid JSON conforming to this schema:\n"
        f"{schema_str}\n\n"
        f"Return ONLY valid JSON, no markdown, no extra text."
    )


# ---------------------------------------------------------------------------
# System prompts (schemas are embedded at call time)
# ---------------------------------------------------------------------------

ANSWER_EVALUATION_INSTRUCTIONS = """You are a technical interviewer evaluating a candidate's answer.
Assess the answer based on:
- 5: Excellent — complete understanding, examples, edge cases considered
- 4: Good — solid understanding with minor omissions
- 3: Adequate — basic understanding but lacks depth
- 2: Weak — significant gaps in understanding
- 1: Poor — incorrect or no meaningful answer

If the answer scores 3 or below, set follow_up_needed to true and provide a
follow_up_question that probes deeper into the topic. Do not set follow_up_needed
if the answer is already comprehensive (score 4-5)."""

FOLLOW_UP_EVALUATION_INSTRUCTIONS = """You are a technical interviewer evaluating a candidate's follow-up answer.
You have the original question, the candidate's initial answer, the follow-up question,
and their follow-up answer. Evaluate the follow-up answer on a scale of 1-5:
- 5: Excellent — deep understanding, insightful
- 4: Good — solid follow-up
- 3: Adequate — acceptable but shallow
- 2: Weak — still not grasping the concept
- 1: Poor — unable to answer

If the follow-up scores 2 or below AND this is not the second follow-up,
you may set needs_further_follow_up to true with another question.
Otherwise set it to false."""

SESSION_EVALUATION_INSTRUCTIONS = """You are a technical interviewer providing a final evaluation.
Review all the question-answer pairs from the interview and provide:
1. Overall narrative feedback summarizing the candidate's performance
2. Topics they should review
3. Key strengths demonstrated
4. A per-question score breakdown

For score_breakdown, use question IDs as keys. Each value is an object
with "score" (sum of all rounds for that question) and "max" fields."""

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class InterviewEvaluatorService:
    """Service for AI-powered evaluation of interview answers.

    Uses the configured AI provider to evaluate answers, generate follow-up
    questions, and produce final session evaluations.
    """

    MAX_FOLLOW_UP_DEPTH = 2

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(content: str, model: type[T]) -> T:
        """Parse AI JSON response and validate against a Pydantic model.

        Strips optional markdown code fences before parsing.

        Args:
            content: Raw JSON string from the AI.
            model: Pydantic model class to validate against.

        Returns:
            Validated Pydantic model instance.

        Raises:
            ValueError: If JSON is invalid or doesn't match the model.
        """
        content = content.strip()

        # Strip markdown code blocks if present
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI returned invalid JSON: {e}") from e

        try:
            return model.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"AI response validation failed: {e}") from e

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    async def evaluate_answer(
        provider: AIProvider,
        question_text: str,
        answer_text: str,
        question_code: str | None = None,
    ) -> AnswerEvaluation:
        """Evaluate a user's initial answer (round=0).

        Builds a prompt with the question context and sends it to the AI
        provider for evaluation.

        Args:
            provider: Configured AI provider instance.
            question_text: The question text.
            answer_text: The user's answer.
            question_code: Optional code snippet from the question.

        Returns:
            AnswerEvaluation with score, feedback, and follow-up decision.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        question = question_text
        if question_code:
            question += f"\n\nCode:\n{question_code}"

        system_prompt = _build_prompt_with_schema(
            ANSWER_EVALUATION_INSTRUCTIONS, AnswerEvaluation
        )

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

        return InterviewEvaluatorService._parse_json_response(
            result.content, AnswerEvaluation
        )

    @staticmethod
    async def evaluate_follow_up(
        provider: AIProvider,
        question_text: str,
        initial_answer: str,
        follow_up_question: str,
        follow_up_answer: str,
        question_code: str | None = None,
    ) -> FollowUpEvaluation:
        """Evaluate a user's follow-up answer (round >= 1).

        Includes the full conversation history for context so the AI can
        assess improvement.

        Args:
            provider: Configured AI provider instance.
            question_text: The original question text.
            initial_answer: The user's initial answer.
            follow_up_question: The follow-up question text.
            follow_up_answer: The user's follow-up answer.
            question_code: Optional code snippet from the question.

        Returns:
            FollowUpEvaluation with score and further follow-up decision.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        question = question_text
        if question_code:
            question += f"\n\nCode:\n{question_code}"

        system_prompt = _build_prompt_with_schema(
            FOLLOW_UP_EVALUATION_INSTRUCTIONS, FollowUpEvaluation
        )

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

        return InterviewEvaluatorService._parse_json_response(
            result.content, FollowUpEvaluation
        )

    @staticmethod
    async def evaluate_session(
        provider: AIProvider,
        questions_answers: list[dict[str, Any]],
        level: str,
        category: str,
    ) -> SessionEvaluation:
        """Provide a final evaluation of an entire interview session.

        Aggregates all Q&A pairs and sends them to the AI for a
        comprehensive summary evaluation.

        Args:
            provider: Configured AI provider instance.
            questions_answers: List of dicts with question_id, question_text,
                answer_text, score, round for each answer.
            level: Interview difficulty level (junior, middle, senior).
            category: Question category (e.g., python).

        Returns:
            SessionEvaluation with overall feedback and recommendations.

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

        system_prompt = _build_prompt_with_schema(
            SESSION_EVALUATION_INSTRUCTIONS, SessionEvaluation
        )

        messages = [
            Message(role="system", content=system_prompt),
            Message(
                role="user",
                content=(
                    f"Interview Level: {level}\n"
                    f"Category: {category}\n\n"
                    f"Questions and Answers:\n{summary_text}"
                ),
            ),
        ]

        result = await provider.generate(
            messages=messages, temperature=0.3, max_tokens=1500
        )

        return InterviewEvaluatorService._parse_json_response(
            result.content, SessionEvaluation
        )
