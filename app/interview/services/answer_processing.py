# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Answer processing service.

Orchestrates answer submission and timeout flows via timer and evaluation services.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.ai.base import AIProvider
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.mappers import interview_read_from_orm
from app.interview.services.answer_ai_evaluation import AnswerAiEvaluationService
from app.interview.services.answer_evaluation_persistence import (
    AnswerEvaluationPersistenceService,
)
from app.interview.services.answer_timer import RoundTimerService
from app.interview.services.events import (
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewEvent,
)
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.progress import (
    find_unanswered_for_question,
    require_active,
)
from app.interview.services.rules.timer import client_timeout_due, is_expired
from app.shared.exceptions import (
    QuestionTimerNotEnabledError,
    QuestionTimerNotExpiredError,
)


class AnswerProcessingService:
    """Orchestrates answer submission, timeout handling, and event streaming."""

    @staticmethod
    async def stream_timeout_submission(
        interview_id: str,
        question_id: str,
        round_num: int,
    ) -> AsyncIterator[InterviewEvent]:
        """Record a timed-out round with zero score and advance the interview.

        Args:
            interview_id: The interview UUID.
            question_id: The question ID.
            round_num: The answer round that expired.

        Yields:
            ``AnswerFeedbackEvent`` when the timeout is accepted.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is already completed.
            QuestionTimerNotEnabledError: If the interview has no time limit.
            QuestionTimerNotExpiredError: If the deadline has not passed yet.
            UnansweredAnswerNotFoundError: If the round is not open.
        """
        with InterviewUnitOfWork() as uow:
            interview_orm = InterviewQuery.get_orm_or_raise(interview_id, uow=uow)
            interview = interview_read_from_orm(interview_orm)
            require_active(interview)

            limit = interview.question_time_limit_seconds
            if not limit:
                raise QuestionTimerNotEnabledError(interview_id)

            db_answer = uow.answers.get_by_interview_question_round(
                interview_id, question_id, round_num
            )
            now = datetime.now(UTC)

            if db_answer.answer_text is not None:
                return

            if not client_timeout_due(db_answer.started_at, limit, now):
                raise QuestionTimerNotExpiredError(interview_id, question_id)

            order = db_answer.order
            locale = interview.locale

        yield RoundTimerService.persist_timed_out_round(
            interview_id=interview_id,
            question_id=question_id,
            round_num=round_num,
            order=order,
            locale=locale,
        )

    @staticmethod
    async def stream_answer_submission(
        interview_id: str,
        question_id: str,
        answer_text: str,
        provider: AIProvider,
    ) -> AsyncIterator[InterviewEvent]:
        """Submit an answer, yield events as each step completes.

        Yields ``AnswerSavedEvent`` and ``EvaluatingEvent`` immediately after the
        answer text is persisted, then runs AI evaluation, then yields feedback.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: The user's answer.
            provider: AI provider for evaluation.

        Yields:
            Semantic events for WebSocket delivery in order.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is already completed.
            UnansweredAnswerNotFoundError: If the question has no open answer row.
            AnswerNotFoundError: If the answer row is missing in the database.
        """
        with InterviewUnitOfWork(auto_commit=True) as uow:
            interview_orm = InterviewQuery.get_orm_or_raise(interview_id, uow=uow)
            interview = interview_read_from_orm(interview_orm)
            require_active(interview)

            current_answer = find_unanswered_for_question(interview, question_id)
            round_num = current_answer.round
            limit = interview.question_time_limit_seconds

            if limit and is_expired(current_answer.started_at, limit, grace_seconds=0):
                async for event in AnswerProcessingService.stream_timeout_submission(
                    interview_id=interview_id,
                    question_id=question_id,
                    round_num=round_num,
                ):
                    yield event
                return

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

        (
            evaluation,
            follow_up_needed,
            follow_up_text,
        ) = await asyncio.shield(
            AnswerAiEvaluationService.evaluate(
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
        )

        yield AnswerEvaluationPersistenceService.persist(
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
        provider: AIProvider,
    ) -> list[InterviewEvent]:
        """Submit an answer and evaluate it with AI.

        Collects all events from ``stream_answer_submission`` for tests and callers
        that need a list.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: The user's answer.
            provider: AI provider for evaluation.

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
                provider=provider,
            )
        ]

    @staticmethod
    async def process_timeout_submission(
        interview_id: str,
        question_id: str,
        round_num: int,
    ) -> list[InterviewEvent]:
        """Process a client timeout and return collected events.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            round_num: The answer round that expired.

        Returns:
            Semantic events in delivery order.
        """
        return [
            event
            async for event in AnswerProcessingService.stream_timeout_submission(
                interview_id=interview_id,
                question_id=question_id,
                round_num=round_num,
            )
        ]
