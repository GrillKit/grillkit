# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""AI-powered theory task evaluation service."""

from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.base import AIProvider, Message
from app.shared.evaluation_models import InterviewEvaluation, SectionEvaluation
from app.shared.locales import DEFAULT_LOCALE
from app.shared.structured_evaluation import (
    evaluate_with_schema,
    generate_and_parse_json_response,
)
from app.theory.services.evaluator.models import (
    AnswerEvaluation,
    FollowUpEvaluation,
)
from app.theory.services.evaluator.prompts import (
    ANSWER_EVALUATION_INSTRUCTIONS,
    FOLLOW_UP_EVALUATION_INSTRUCTIONS,
    SECTION_EVALUATION_INSTRUCTIONS,
    SESSION_EVALUATION_INSTRUCTIONS,
    build_evaluator_instructions,
    looks_like_json_schema_fragment,
)

__all__ = [
    "AnswerEvaluation",
    "FollowUpEvaluation",
    "InterviewEvaluation",
    "SectionEvaluation",
    "TheoryEvaluatorService",
    "looks_like_json_schema_fragment",
]

T = TypeVar("T", bound=BaseModel)


class TheoryEvaluatorService:
    """Service for AI-powered evaluation of theory task answers.

    Uses the configured AI provider to evaluate answers, generate follow-up
    questions, and produce final session evaluations.
    """

    MAX_FOLLOW_UP_DEPTH = 2

    @staticmethod
    def _format_question(question_text: str, question_code: str | None) -> str:
        """Append optional code block to question text for prompts.

        Args:
            question_text: Base question text.
            question_code: Optional code snippet.

        Returns:
            Question text, with code block when provided.
        """
        if question_code:
            return f"{question_text}\n\nCode:\n{question_code}"
        return question_text

    @staticmethod
    async def _evaluate_with_schema(
        provider: AIProvider,
        *,
        locale: str,
        instructions: str,
        response_model: type[T],
        user_text: str,
        audio_wav: bytes | None = None,
        max_tokens: int = 2000,
    ) -> T:
        """Run a structured evaluation via text or multimodal generation.

        Args:
            provider: Configured AI provider instance.
            locale: Locale for AI feedback.
            instructions: Evaluator instruction template constant.
            response_model: Pydantic model for parsed JSON output.
            user_text: User message text (full content for text mode; context for audio).
            audio_wav: Optional WAV bytes for multimodal evaluation.
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
            audio_wav=audio_wav,
            max_tokens=max_tokens,
        )

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
        question = TheoryEvaluatorService._format_question(question_text, question_code)
        user_text = f"Question:\n{question}\n\nAnswer:\n{answer_text}"
        return await TheoryEvaluatorService._evaluate_with_schema(
            provider,
            locale=locale,
            instructions=ANSWER_EVALUATION_INSTRUCTIONS,
            response_model=AnswerEvaluation,
            user_text=user_text,
        )

    @staticmethod
    async def evaluate_answer_with_audio(
        provider: AIProvider,
        question_text: str,
        audio_wav: bytes,
        question_code: str | None = None,
        locale: str = DEFAULT_LOCALE,
    ) -> AnswerEvaluation:
        """Evaluate a user's initial spoken answer (round=0).

        Args:
            provider: Configured AI provider instance.
            question_text: The question text.
            audio_wav: The user's spoken answer as WAV bytes.
            question_code: Optional code snippet from the question.
            locale: Locale for AI feedback and follow-up questions.

        Returns:
            AnswerEvaluation with score, feedback, and follow-up decision.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        question = TheoryEvaluatorService._format_question(question_text, question_code)
        return await TheoryEvaluatorService._evaluate_with_schema(
            provider,
            locale=locale,
            instructions=ANSWER_EVALUATION_INSTRUCTIONS,
            response_model=AnswerEvaluation,
            user_text=f"Question:\n{question}",
            audio_wav=audio_wav,
        )

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
        question = TheoryEvaluatorService._format_question(question_text, question_code)
        user_text = (
            f"Original Question:\n{question}\n\n"
            f"Initial Answer:\n{initial_answer}\n\n"
            f"Follow-up Question:\n{follow_up_question}\n\n"
            f"Follow-up Answer:\n{follow_up_answer}"
        )
        return await TheoryEvaluatorService._evaluate_with_schema(
            provider,
            locale=locale,
            instructions=FOLLOW_UP_EVALUATION_INSTRUCTIONS,
            response_model=FollowUpEvaluation,
            user_text=user_text,
        )

    @staticmethod
    async def evaluate_follow_up_with_audio(
        provider: AIProvider,
        question_text: str,
        initial_answer: str,
        follow_up_question: str,
        audio_wav: bytes,
        question_code: str | None = None,
        locale: str = DEFAULT_LOCALE,
    ) -> FollowUpEvaluation:
        """Evaluate a user's spoken follow-up answer (round >= 1).

        Args:
            provider: Configured AI provider instance.
            question_text: The original question text.
            initial_answer: The user's initial answer text (transcript).
            follow_up_question: The follow-up question text.
            audio_wav: The user's spoken follow-up answer as WAV bytes.
            question_code: Optional code snippet from the question.
            locale: Locale for AI feedback and follow-up questions.

        Returns:
            FollowUpEvaluation with score and further follow-up decision.

        Raises:
            ValueError: If AI response is invalid or connection fails.
        """
        question = TheoryEvaluatorService._format_question(question_text, question_code)
        user_text = (
            f"Original Question:\n{question}\n\n"
            f"Initial Answer:\n{initial_answer}\n\n"
            f"Follow-up Question:\n{follow_up_question}"
        )
        return await TheoryEvaluatorService._evaluate_with_schema(
            provider,
            locale=locale,
            instructions=FOLLOW_UP_EVALUATION_INSTRUCTIONS,
            response_model=FollowUpEvaluation,
            user_text=user_text,
            audio_wav=audio_wav,
        )

    @staticmethod
    def _follow_up_decision(
        evaluation: AnswerEvaluation | FollowUpEvaluation,
        answer_round: int,
    ) -> tuple[bool, str | None]:
        """Decide whether another follow-up round is needed after evaluation.

        Args:
            evaluation: Parsed AI evaluation for the submitted round.
            answer_round: Follow-up round that was evaluated (0 = initial).

        Returns:
            Tuple of (follow_up_needed, follow_up_question_text).
        """
        if answer_round == 0:
            if not isinstance(evaluation, AnswerEvaluation):
                raise TypeError("Round 0 evaluation must be AnswerEvaluation")
            follow_up_needed = evaluation.follow_up_needed and bool(
                evaluation.follow_up_question
            )
            return follow_up_needed, evaluation.follow_up_question
        if not isinstance(evaluation, FollowUpEvaluation):
            raise TypeError("Follow-up round evaluation must be FollowUpEvaluation")
        follow_up_needed = (
            evaluation.needs_further_follow_up
            and bool(evaluation.follow_up_question)
            and answer_round < TheoryEvaluatorService.MAX_FOLLOW_UP_DEPTH
        )
        return follow_up_needed, evaluation.follow_up_question

    @staticmethod
    async def evaluate_submission(
        *,
        provider: AIProvider,
        locale: str,
        answer_round: int,
        question_text: str,
        question_code: str | None,
        initial_question_text: str,
        initial_answer_text: str,
        answer_text: str | None = None,
        audio_wav: bytes | None = None,
    ) -> tuple[AnswerEvaluation | FollowUpEvaluation, bool, str | None]:
        """Evaluate one answer round and decide whether a follow-up is needed.

        Args:
            provider: Configured AI provider instance.
            locale: Locale for AI feedback and follow-up questions.
            answer_round: Follow-up round (0 = initial).
            question_text: Text of the question being answered.
            question_code: Optional code snippet for the question.
            initial_question_text: Original question text (round 0).
            initial_answer_text: User's initial answer text (round 0).
            answer_text: User answer text for text-mode evaluation.
            audio_wav: Spoken answer WAV for multimodal evaluation.

        Returns:
            Tuple of (evaluation, follow_up_needed, follow_up_text).

        Raises:
            ValueError: If neither or both of ``answer_text`` and ``audio_wav`` are set.
        """
        if (answer_text is None) == (audio_wav is None):
            raise ValueError("Provide exactly one of answer_text or audio_wav")

        evaluation: AnswerEvaluation | FollowUpEvaluation
        if answer_round == 0:
            if audio_wav is not None:
                evaluation = await TheoryEvaluatorService.evaluate_answer_with_audio(
                    provider=provider,
                    question_text=question_text,
                    audio_wav=audio_wav,
                    question_code=question_code,
                    locale=locale,
                )
            else:
                evaluation = await TheoryEvaluatorService.evaluate_answer(
                    provider=provider,
                    question_text=question_text,
                    answer_text=answer_text or "",
                    question_code=question_code,
                    locale=locale,
                )
        elif audio_wav is not None:
            evaluation = await TheoryEvaluatorService.evaluate_follow_up_with_audio(
                provider=provider,
                question_text=initial_question_text,
                initial_answer=initial_answer_text,
                follow_up_question=question_text,
                audio_wav=audio_wav,
                question_code=question_code,
                locale=locale,
            )
        else:
            evaluation = await TheoryEvaluatorService.evaluate_follow_up(
                provider=provider,
                question_text=initial_question_text,
                initial_answer=initial_answer_text,
                follow_up_question=question_text,
                follow_up_answer=answer_text or "",
                question_code=question_code,
                locale=locale,
            )

        follow_up_needed, follow_up_text = TheoryEvaluatorService._follow_up_decision(
            evaluation, answer_round
        )
        return evaluation, follow_up_needed, follow_up_text

    @staticmethod
    async def evaluate_section(
        provider: AIProvider,
        questions_answers: list[dict[str, Any]],
        sources_text: str,
        locale: str = DEFAULT_LOCALE,
    ) -> SectionEvaluation:
        """Provide a narrative evaluation for one interview section.

        Args:
            provider: Configured AI provider instance.
            questions_answers: Per-task Q&A rows for the section.
            sources_text: Human-readable list of tracks, levels, and topics.
            locale: Locale for the section evaluation narrative.

        Returns:
            SectionEvaluation with narrative feedback and recommendations.

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
        user_text = f"Sources:\n{sources_text}\n\nSection Questions and Answers:\n{summary_text}"
        return await TheoryEvaluatorService._evaluate_with_schema(
            provider,
            locale=locale,
            instructions=SECTION_EVALUATION_INSTRUCTIONS,
            response_model=SectionEvaluation,
            user_text=user_text,
            max_tokens=2000,
        )

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
        user_text = (
            f"Sources:\n{sources_text}\n\nQuestions and Answers:\n{summary_text}"
        )
        system_prompt = (
            f"{build_evaluator_instructions(locale, SESSION_EVALUATION_INSTRUCTIONS)}\n\n"
            "Return ONLY one valid JSON object with overall_feedback, "
            "topics_to_review, and strengths_summary. "
            "Do not include score_breakdown. "
            "No markdown fences, no extra text."
        )
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_text),
        ]
        return await generate_and_parse_json_response(
            provider,
            messages=messages,
            response_model=InterviewEvaluation,
            max_tokens=2000,
        )
