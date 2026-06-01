# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Answer processing service.

Orchestrates text and audio answer submission, timeout flows, and event streaming.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
import logging

from app.ai.base import AIProvider
from app.ai.speech_transcriber import SpeechTranscriber
from app.interview.domain.exceptions import (
    InterviewNotFoundError,
    QuestionTimerNotEnabledError,
    QuestionTimerNotExpiredError,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.answer_ai_evaluation import AnswerAiEvaluationService
from app.interview.services.answer_evaluation_persistence import (
    AnswerEvaluationPersistenceService,
)
from app.interview.services.answer_timer import RoundTimerService
from app.interview.services.evaluator.service import InterviewEvaluatorService
from app.interview.services.events import (
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewEvent,
    TranscriptEvent,
)
from app.platform.services.config import ConfigService
from app.platform.services.llm_catalog import LLMCatalogService
from app.shared.infrastructure.audio_wav import (
    validate_wav_bytes,
    wav_bytes_to_float32,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnswerSubmissionContext:
    """Shared state after an answer row is opened for submission.

    Attributes:
        question_id: YAML question ID.
        round_num: Follow-up round (0 = initial).
        order: Display order of the answer.
        question_text: Text of the question being answered.
        question_code: Optional code snippet for the question.
        initial_question_text: Original question text (round 0).
        initial_answer_text: User's initial answer text (round 0).
        locale: Interview locale for AI and speech.
        answer_text: Text persisted on the answer row (may be empty for audio).
    """

    question_id: str
    round_num: int
    order: int
    question_text: str
    question_code: str | None
    initial_question_text: str
    initial_answer_text: str
    locale: str
    answer_text: str


async def _evaluate_last_follow_up_in_background(
    *,
    interview_id: str,
    question_id: str,
    round_num: int,
    question_text: str,
    question_code: str | None,
    answer_text: str,
    initial_question_text: str,
    initial_answer_text: str,
    provider: AIProvider,
    locale: str,
    audio_wav: bytes | None = None,
) -> None:
    """Run AI evaluation for the last follow-up round and persist score only.

    Args:
        interview_id: The session UUID.
        question_id: The question ID.
        round_num: The follow-up round that was submitted.
        question_text: Text of the follow-up question.
        question_code: Optional code snippet for the question.
        answer_text: The user's answer text (transcript when audio was submitted).
        initial_question_text: Original question text (round 0).
        initial_answer_text: User's initial answer text (round 0).
        provider: AI provider for evaluation.
        locale: Locale for AI feedback.
        audio_wav: Optional spoken answer WAV for multimodal evaluation.
    """
    try:
        if audio_wav is not None:
            evaluation, _, _ = await AnswerAiEvaluationService.evaluate_with_audio(
                answer_round=round_num,
                question_text=question_text,
                question_code=question_code,
                audio_wav=audio_wav,
                initial_question_text=initial_question_text,
                initial_answer_text=initial_answer_text,
                provider=provider,
                locale=locale,
            )
        else:
            evaluation, _, _ = await AnswerAiEvaluationService.evaluate(
                answer_round=round_num,
                question_text=question_text,
                question_code=question_code,
                answer_text=answer_text,
                initial_question_text=initial_question_text,
                initial_answer_text=initial_answer_text,
                provider=provider,
                locale=locale,
            )
        AnswerEvaluationPersistenceService.persist_evaluation_only(
            interview_id=interview_id,
            question_id=question_id,
            round_num=round_num,
            evaluation=evaluation,
        )
    except Exception:
        logger.exception(
            "Background evaluation failed for interview=%s question=%s round=%s",
            interview_id,
            question_id,
            round_num,
        )


class AnswerProcessingService:
    """Orchestrates answer submission, timeout handling, and event streaming."""

    @staticmethod
    def require_audio_answer_enabled() -> None:
        """Ensure the selected catalog model accepts audio input.

        Raises:
            ValueError: When configuration or catalog flags disallow audio answers.
        """
        config = ConfigService.get_config()
        if config is None or not config.llm_preset_id:
            raise ValueError("Interview model is not configured")
        entry = LLMCatalogService.get_model(config.llm_preset_id)
        if entry is None or not entry.accepts_audio_input:
            raise ValueError("Selected interview model does not accept audio input")

    @staticmethod
    async def _open_submission(
        interview_id: str,
        question_id: str,
        answer_text: str,
    ) -> AsyncIterator[AnswerSubmissionContext | InterviewEvent]:
        """Validate the session and persist answer text before evaluation.

        Yields timeout events when the round expired, otherwise one
        :class:`AnswerSubmissionContext`.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: Text to store on the answer row (empty for audio).

        Yields:
            Timeout feedback events or a single submission context.
        """
        timed_out_round: int | None = None
        submission: AnswerSubmissionContext | None = None

        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)

            aggregate.ensure_active()
            current = aggregate.find_unanswered_for_question(question_id)
            round_num = current.round
            limit = aggregate.question_time_limit_seconds

            if limit and current.is_timer_expired(limit, grace_seconds=0):
                timed_out_round = round_num
            else:
                updated = aggregate.with_answer_text(current.id, answer_text)
                uow.interviews.save_aggregate(updated)
                saved = next(a for a in updated.answers if a.id == current.id)

                initial_question_text = saved.question_text
                initial_answer_text = ""
                if round_num > 0:
                    initial = next(
                        a
                        for a in updated.answers
                        if a.question_id == question_id and a.round == 0
                    )
                    initial_question_text = initial.question_text
                    initial_answer_text = initial.answer_text or ""

                submission = AnswerSubmissionContext(
                    question_id=question_id,
                    round_num=round_num,
                    order=saved.order,
                    question_text=saved.question_text,
                    question_code=saved.question_code,
                    initial_question_text=initial_question_text,
                    initial_answer_text=initial_answer_text,
                    locale=updated.locale,
                    answer_text=answer_text,
                )

        if timed_out_round is not None:
            async for event in AnswerProcessingService.stream_timeout_submission(
                interview_id=interview_id,
                question_id=question_id,
                round_num=timed_out_round,
            ):
                yield event
            return

        if submission is not None:
            yield submission

    @staticmethod
    async def _transcribe_and_persist(
        *,
        interview_id: str,
        question_id: str,
        round_num: int,
        wav_bytes: bytes,
        transcriber: SpeechTranscriber,
        locale: str,
    ) -> str:
        """Transcribe WAV audio and persist the answer text.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the answer row.
            round_num: Follow-up round being answered.
            wav_bytes: Canonical WAV payload.
            transcriber: Loaded speech transcriber.
            locale: Interview locale for recognition.

        Returns:
            Final transcript text (may be empty).
        """
        samples = wav_bytes_to_float32(wav_bytes)
        transcript = await transcriber.transcribe(samples, locale)
        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)
            current = aggregate.find_answer(question_id, round_num)
            updated = aggregate.with_answer_text(current.id, transcript)
            uow.interviews.save_aggregate(updated)
        return transcript

    @staticmethod
    def _schedule_last_follow_up_evaluation(
        *,
        interview_id: str,
        ctx: AnswerSubmissionContext,
        provider: AIProvider,
        audio_wav: bytes | None = None,
    ) -> None:
        """Run last-round AI evaluation in the background.

        Args:
            interview_id: Interview UUID.
            ctx: Open submission context.
            provider: AI provider for evaluation.
            audio_wav: Optional spoken answer WAV for multimodal evaluation.
        """
        asyncio.create_task(
            _evaluate_last_follow_up_in_background(
                interview_id=interview_id,
                question_id=ctx.question_id,
                round_num=ctx.round_num,
                question_text=ctx.question_text,
                question_code=ctx.question_code,
                answer_text=ctx.answer_text,
                initial_question_text=ctx.initial_question_text,
                initial_answer_text=ctx.initial_answer_text,
                provider=provider,
                locale=ctx.locale,
                audio_wav=audio_wav,
            ),
            name=(
                f"bg-{'audio-' if audio_wav is not None else ''}eval-"
                f"{interview_id}-{ctx.question_id}-r{ctx.round_num}"
            ),
        )

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
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                raise InterviewNotFoundError(interview_id)

            aggregate.ensure_active()

            limit = aggregate.question_time_limit_seconds
            if not limit:
                raise QuestionTimerNotEnabledError(interview_id)

            current = aggregate.find_answer(question_id, round_num)
            now = datetime.now(UTC)

            if current.answer_text is not None:
                return

            if not current.client_timeout_due(limit, now):
                raise QuestionTimerNotExpiredError(interview_id, question_id)

            order = current.order
            locale = aggregate.locale

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
        """Submit a text answer and yield events as each step completes.

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
        ctx: AnswerSubmissionContext | None = None
        async for item in AnswerProcessingService._open_submission(
            interview_id, question_id, answer_text
        ):
            if isinstance(item, AnswerSubmissionContext):
                ctx = item
                break
            yield item
        if ctx is None:
            return

        if ctx.round_num >= InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH:
            yield AnswerSavedEvent()
            yield AnswerEvaluationPersistenceService.advance_without_evaluation(
                interview_id=interview_id,
                question_id=ctx.question_id,
                round_num=ctx.round_num,
                order=ctx.order,
            )
            AnswerProcessingService._schedule_last_follow_up_evaluation(
                interview_id=interview_id,
                ctx=ctx,
                provider=provider,
            )
            return

        yield AnswerSavedEvent()
        yield EvaluatingEvent()

        (
            evaluation,
            follow_up_needed,
            follow_up_text,
        ) = await asyncio.shield(
            AnswerAiEvaluationService.evaluate(
                answer_round=ctx.round_num,
                question_text=ctx.question_text,
                question_code=ctx.question_code,
                answer_text=ctx.answer_text,
                initial_question_text=ctx.initial_question_text,
                initial_answer_text=ctx.initial_answer_text,
                provider=provider,
                locale=ctx.locale,
            )
        )

        yield AnswerEvaluationPersistenceService.persist(
            interview_id=interview_id,
            question_id=ctx.question_id,
            round_num=ctx.round_num,
            order=ctx.order,
            evaluation=evaluation,
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
        )

    @staticmethod
    async def stream_audio_answer_submission(
        interview_id: str,
        question_id: str,
        wav_bytes: bytes,
        provider: AIProvider,
        transcriber: SpeechTranscriber,
    ) -> AsyncIterator[InterviewEvent]:
        """Submit an audio answer and yield NDJSON-compatible service events.

        Whisper transcription and LLM audio evaluation run in parallel after the
        answer row is saved. On the last allowed follow-up round, navigation
        happens immediately and LLM evaluation continues in the background.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            wav_bytes: Canonical mono 16 kHz PCM WAV bytes.
            provider: AI provider for multimodal evaluation.
            transcriber: Loaded speech transcriber for transcript persistence.

        Yields:
            Semantic events for HTTP NDJSON or WebSocket delivery.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is already completed.
            UnansweredAnswerNotFoundError: If the question has no open answer row.
            AnswerNotFoundError: If the answer row is missing in the database.
            ValueError: If WAV validation or audio capability checks fail.
        """
        AnswerProcessingService.require_audio_answer_enabled()
        validate_wav_bytes(wav_bytes)

        ctx: AnswerSubmissionContext | None = None
        async for item in AnswerProcessingService._open_submission(
            interview_id, question_id, ""
        ):
            if isinstance(item, AnswerSubmissionContext):
                ctx = item
                break
            yield item
        if ctx is None:
            return

        yield AnswerSavedEvent()

        if ctx.round_num >= InterviewEvaluatorService.MAX_FOLLOW_UP_DEPTH:
            yield AnswerEvaluationPersistenceService.advance_without_evaluation(
                interview_id=interview_id,
                question_id=ctx.question_id,
                round_num=ctx.round_num,
                order=ctx.order,
            )
            transcript_task = asyncio.create_task(
                AnswerProcessingService._transcribe_and_persist(
                    interview_id=interview_id,
                    question_id=ctx.question_id,
                    round_num=ctx.round_num,
                    wav_bytes=wav_bytes,
                    transcriber=transcriber,
                    locale=ctx.locale,
                ),
                name=f"audio-transcript-{interview_id}-{ctx.question_id}-r{ctx.round_num}",
            )
            AnswerProcessingService._schedule_last_follow_up_evaluation(
                interview_id=interview_id,
                ctx=ctx,
                provider=provider,
                audio_wav=wav_bytes,
            )
            transcript = await transcript_task
            yield TranscriptEvent(
                question_id=ctx.question_id,
                round=ctx.round_num,
                text=transcript,
            )
            return

        yield EvaluatingEvent()

        transcript_task = asyncio.create_task(
            AnswerProcessingService._transcribe_and_persist(
                interview_id=interview_id,
                question_id=ctx.question_id,
                round_num=ctx.round_num,
                wav_bytes=wav_bytes,
                transcriber=transcriber,
                locale=ctx.locale,
            ),
            name=f"audio-transcript-{interview_id}-{ctx.question_id}-r{ctx.round_num}",
        )
        evaluation_task = asyncio.create_task(
            AnswerAiEvaluationService.evaluate_with_audio(
                answer_round=ctx.round_num,
                question_text=ctx.question_text,
                question_code=ctx.question_code,
                audio_wav=wav_bytes,
                initial_question_text=ctx.initial_question_text,
                initial_answer_text=ctx.initial_answer_text,
                provider=provider,
                locale=ctx.locale,
            ),
            name=f"audio-eval-{interview_id}-{ctx.question_id}-r{ctx.round_num}",
        )

        transcript = await transcript_task
        yield TranscriptEvent(
            question_id=ctx.question_id,
            round=ctx.round_num,
            text=transcript,
        )

        (
            evaluation,
            follow_up_needed,
            follow_up_text,
        ) = await asyncio.shield(evaluation_task)

        yield AnswerEvaluationPersistenceService.persist(
            interview_id=interview_id,
            question_id=ctx.question_id,
            round_num=ctx.round_num,
            order=ctx.order,
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
        """Submit a text answer and collect all stream events.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: The user's answer.
            provider: AI provider for evaluation.

        Returns:
            Semantic events in delivery order.
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
    async def process_audio_answer_submission(
        interview_id: str,
        question_id: str,
        wav_bytes: bytes,
        provider: AIProvider,
        transcriber: SpeechTranscriber,
    ) -> list[InterviewEvent]:
        """Submit an audio answer and collect all stream events.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            wav_bytes: Canonical mono 16 kHz PCM WAV bytes.
            provider: AI provider for multimodal evaluation.
            transcriber: Loaded speech transcriber.

        Returns:
            Semantic events in delivery order.
        """
        return [
            event
            async for event in AnswerProcessingService.stream_audio_answer_submission(
                interview_id=interview_id,
                question_id=question_id,
                wav_bytes=wav_bytes,
                provider=provider,
                transcriber=transcriber,
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
