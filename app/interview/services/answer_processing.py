# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Answer processing service.

This module provides service for processing user answers, evaluating them with AI,
and generating follow-up questions.
"""

from collections.abc import AsyncIterator
import logging
from typing import Any

from app.ai.base import AIProvider
from app.interview.domain.progress import (
    find_next_unanswered_after,
    find_unanswered_for_question,
    require_active,
)
from app.interview.services.evaluator.service import (
    AnswerEvaluation,
    FollowUpEvaluation,
    InterviewEvaluatorService,
)
from app.interview.services.events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewEvent,
)
from app.interview.services.query import InterviewQuery
from app.platform.services.ai_context import ai_provider_from_config
from app.shared.infrastructure.models import Answer
from app.shared.infrastructure.uow import UnitOfWork

logger = logging.getLogger(__name__)


class AnswerProcessingService:
    """Service for processing user answers and AI evaluation."""

    @staticmethod
    async def _run_ai_evaluation(
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
            locale: Language for AI feedback and follow-up questions.

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

    @staticmethod
    def _persist_evaluation(
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        order: int,
        evaluation: AnswerEvaluation | FollowUpEvaluation,
        follow_up_needed: bool,
        follow_up_text: str | None,
    ) -> AnswerFeedbackEvent:
        """Save AI evaluation results and build a feedback event.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the answer row.
            round_num: Follow-up round (0 = initial).
            order: Display order of the answer.
            evaluation: Parsed AI evaluation.
            follow_up_needed: Whether to create a follow-up row.
            follow_up_text: Follow-up question text when applicable.

        Returns:
            Feedback event for the client.
        """
        next_question_data: dict[str, Any] | None = None
        with UnitOfWork(auto_commit=True) as uow:
            db_interview = InterviewQuery.get_interview_or_raise(interview_id, uow=uow)

            db_answer = uow.answers.get_by_interview_question_round(
                interview_id=interview_id,
                question_id=question_id,
                round_num=round_num,
            )
            uow.answers.set_evaluation(db_answer, evaluation.score, evaluation.feedback)

            if follow_up_needed:
                max_round = uow.answers.get_max_round(interview_id, question_id)
                next_round = max_round + 1

                original = uow.answers.get_by_interview_question_round(
                    interview_id, question_id, 0
                )
                follow_up = Answer(
                    interview_id=original.interview_id,
                    question_id=original.question_id,
                    order=original.order,
                    round=next_round,
                    question_text=follow_up_text or "",
                    question_code=original.question_code,
                )
                uow.answers.add(follow_up)
            else:
                current_index = next(
                    i
                    for i, ans in enumerate(db_interview.answers)
                    if ans.question_id == question_id and ans.round == round_num
                )
                next_question = find_next_unanswered_after(db_interview, current_index)
                if next_question is not None:
                    next_question_data = {
                        "question_id": next_question.question_id,
                        "order": next_question.order,
                        "question_text": next_question.question_text,
                        "question_code": next_question.question_code,
                    }

        return AnswerFeedbackEvent(
            question_id=question_id,
            order=order,
            round=round_num,
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
            next_question=next_question_data,
        )

    @staticmethod
    async def stream_answer_submission(
        interview_id: str,
        question_id: str,
        answer_text: str,
    ) -> AsyncIterator[InterviewEvent]:
        """Submit an answer, yield events as each step completes.

        Yields ``AnswerSavedEvent`` and ``EvaluatingEvent`` immediately after the
        answer text is persisted, then runs AI evaluation, then yields feedback.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: The user's answer.

        Yields:
            Semantic events for WebSocket delivery in order.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is already completed.
            UnansweredAnswerNotFoundError: If the question has no open answer row.
            AnswerNotFoundError: If the answer row is missing in the database.
        """
        with UnitOfWork(auto_commit=True) as uow:
            interview = InterviewQuery.get_interview_or_raise(interview_id, uow=uow)
            require_active(interview)

            current_answer = find_unanswered_for_question(interview, question_id)
            round_num = current_answer.round

            db_answer = uow.answers.get_by_interview_question_round(
                interview_id, question_id, round_num
            )
            uow.answers.set_answer_text(db_answer, answer_text)

            initial_question_text = current_answer.question_text
            initial_answer_text = ""
            if round_num > 0:
                initial = uow.answers.get_by_interview_question_round(
                    interview_id, question_id, 0
                )
                initial_question_text = initial.question_text
                initial_answer_text = initial.answer_text or ""

            question_text = current_answer.question_text
            question_code = current_answer.question_code
            order = current_answer.order
            locale = interview.locale

        yield AnswerSavedEvent()
        yield EvaluatingEvent()

        async with ai_provider_from_config() as provider:
            (
                evaluation,
                follow_up_needed,
                follow_up_text,
            ) = await AnswerProcessingService._run_ai_evaluation(
                question_id=question_id,
                answer_round=round_num,
                question_text=question_text,
                question_code=question_code,
                answer_text=answer_text,
                initial_question_text=initial_question_text,
                initial_answer_text=initial_answer_text,
                provider=provider,
                locale=locale,
            )

        yield AnswerProcessingService._persist_evaluation(
            interview_id=interview_id,
            question_id=question_id,
            round_num=round_num,
            order=order,
            evaluation=evaluation,
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
        )

    @staticmethod
    async def process_answer_submission(
        interview_id: str,
        question_id: str,
        answer_text: str,
    ) -> list[InterviewEvent]:
        """Submit an answer and evaluate it with AI.

        Collects all events from ``stream_answer_submission`` for tests and callers
        that need a list.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: The user's answer.

        Returns:
            Semantic events in delivery order.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is already completed.
            UnansweredAnswerNotFoundError: If the question has no open answer row.
            AnswerNotFoundError: If the answer row is missing in the database.
        """
        return [
            event
            async for event in AnswerProcessingService.stream_answer_submission(
                interview_id=interview_id,
                question_id=question_id,
                answer_text=answer_text,
            )
        ]
