# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory task submission orchestration.

Handles text and audio answer submission, timeout flows, and event streaming.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
import logging

from app.ai.base import AIProvider
from app.ai.speech_transcriber import SpeechTranscriber
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork
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
from app.theory.domain.exceptions import (
    TaskTimerNotEnabledError,
    TaskTimerNotExpiredError,
    TheorySectionNotFoundError,
)
from app.theory.repositories.uow import TheoryUnitOfWork
from app.theory.services.evaluation_persistence import (
    TheoryEvaluationPersistenceService,
)
from app.theory.services.evaluator.service import TheoryEvaluatorService
from app.theory.services.timer import TheoryTimerService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TheorySubmissionContext:
    """Shared state after a theory task row is opened for submission.

    Attributes:
        question_id: YAML question ID.
        round_num: Follow-up round (0 = initial).
        order: Display order of the task.
        question_text: Text of the question being answered.
        question_code: Optional code snippet for the question.
        initial_question_text: Original question text (round 0).
        initial_answer_text: User's initial answer text (round 0).
        expected_points: Rubric bullets for AI evaluation.
        locale: Section locale for AI and speech.
        answer_text: Text persisted on the task row (may be empty for audio).
    """

    question_id: str
    round_num: int
    order: int
    question_text: str
    question_code: str | None
    initial_question_text: str
    initial_answer_text: str
    expected_points: tuple[str, ...]
    locale: str
    answer_text: str


def _ensure_interview_active(interview_id: str) -> None:
    """Ensure the parent interview session accepts submissions.

    Args:
        interview_id: Parent interview UUID.

    Raises:
        InterviewNotFoundError: If the interview does not exist.
        InterviewNotActiveError: If the interview is completed.
    """
    with InterviewUnitOfWork() as uow:
        aggregate = uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            raise InterviewNotFoundError(interview_id)
        aggregate.ensure_active()


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
    expected_points: tuple[str, ...],
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
        expected_points: Rubric bullets for AI evaluation.
        provider: AI provider for evaluation.
        locale: Locale for AI feedback.
        audio_wav: Optional spoken answer WAV for multimodal evaluation.
    """
    try:
        if audio_wav is not None:
            evaluation, _, _ = await TheoryEvaluatorService.evaluate_submission(
                provider=provider,
                locale=locale,
                answer_round=round_num,
                question_text=question_text,
                question_code=question_code,
                initial_question_text=initial_question_text,
                initial_answer_text=initial_answer_text,
                expected_points=expected_points,
                audio_wav=audio_wav,
            )
        else:
            evaluation, _, _ = await TheoryEvaluatorService.evaluate_submission(
                provider=provider,
                locale=locale,
                answer_round=round_num,
                question_text=question_text,
                question_code=question_code,
                initial_question_text=initial_question_text,
                initial_answer_text=initial_answer_text,
                expected_points=expected_points,
                answer_text=answer_text,
            )
        TheoryEvaluationPersistenceService.persist_evaluation_only(
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


class TheorySubmissionService:
    """Orchestrates theory task submission, timeout handling, and event streaming."""

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
    ) -> AsyncIterator[TheorySubmissionContext | InterviewEvent]:
        """Validate the section and persist task text before evaluation.

        Yields timeout events when the round expired, otherwise one
        :class:`TheorySubmissionContext`.

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            answer_text: Text to store on the task row (empty for audio).

        Yields:
            Timeout feedback events or a single submission context.
        """
        timed_out_round: int | None = None
        submission: TheorySubmissionContext | None = None

        _ensure_interview_active(interview_id)

        with TheoryUnitOfWork(auto_commit=True) as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                raise TheorySectionNotFoundError(interview_id)

            section.ensure_active()
            current = section.find_unanswered_for_question(question_id)
            round_num = current.round
            limit = section.task_time_limit_seconds

            if limit and current.is_timer_expired(limit, grace_seconds=0):
                timed_out_round = round_num
            else:
                updated = section.with_task_text(current.id, answer_text)
                uow.theory_sections.save_aggregate(updated)
                saved = next(task for task in updated.tasks if task.id == current.id)

                initial_question_text = saved.question_text
                initial_answer_text = ""
                if round_num > 0:
                    initial = next(
                        task
                        for task in updated.tasks
                        if task.question_id == question_id and task.round == 0
                    )
                    initial_question_text = initial.question_text
                    initial_answer_text = initial.answer_text or ""

                submission = TheorySubmissionContext(
                    question_id=question_id,
                    round_num=round_num,
                    order=saved.order,
                    question_text=saved.question_text,
                    question_code=saved.question_code,
                    initial_question_text=initial_question_text,
                    initial_answer_text=initial_answer_text,
                    expected_points=saved.expected_points,
                    locale=updated.locale,
                    answer_text=answer_text,
                )

        if timed_out_round is not None:
            async for event in TheorySubmissionService.stream_timeout_submission(
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
        """Transcribe WAV audio and persist the task answer text.

        Args:
            interview_id: Interview UUID.
            question_id: Question ID from the task row.
            round_num: Follow-up round being answered.
            wav_bytes: Canonical WAV payload.
            transcriber: Loaded speech transcriber.
            locale: Section locale for recognition.

        Returns:
            Final transcript text (may be empty).
        """
        samples = wav_bytes_to_float32(wav_bytes)
        transcript = await transcriber.transcribe(samples, locale)
        with TheoryUnitOfWork(auto_commit=True) as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                raise TheorySectionNotFoundError(interview_id)
            current = section.find_task(question_id, round_num)
            updated = section.with_task_text(current.id, transcript)
            uow.theory_sections.save_aggregate(updated)
        return transcript

    @staticmethod
    def _schedule_last_follow_up_evaluation(
        *,
        interview_id: str,
        ctx: TheorySubmissionContext,
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
                expected_points=ctx.expected_points,
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
        """Record a timed-out round with zero score and advance the section.

        Args:
            interview_id: The interview UUID.
            question_id: The question ID.
            round_num: The task round that expired.

        Yields:
            ``AnswerFeedbackEvent`` when the timeout is accepted.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is already completed.
            TheorySectionNotFoundError: If the theory section does not exist.
            TaskTimerNotEnabledError: If the section has no time limit.
            TaskTimerNotExpiredError: If the deadline has not passed yet.
            UnansweredTaskNotFoundError: If the round is not open.
        """
        _ensure_interview_active(interview_id)

        with TheoryUnitOfWork() as uow:
            section = uow.theory_sections.get_aggregate(interview_id)
            if section is None:
                raise TheorySectionNotFoundError(interview_id)

            section.ensure_active()

            limit = section.task_time_limit_seconds
            if not limit:
                raise TaskTimerNotEnabledError(interview_id)

            current = section.find_task(question_id, round_num)
            now = datetime.now(UTC)

            if current.answer_text is not None:
                return

            if not current.client_timeout_due(limit, now):
                raise TaskTimerNotExpiredError(interview_id, question_id)

            order = current.order
            locale = section.locale

        yield TheoryTimerService.persist_timed_out_round(
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
        """
        ctx: TheorySubmissionContext | None = None
        async for item in TheorySubmissionService._open_submission(
            interview_id, question_id, answer_text
        ):
            if isinstance(item, TheorySubmissionContext):
                ctx = item
                break
            yield item
        if ctx is None:
            return

        if ctx.round_num >= TheoryEvaluatorService.MAX_FOLLOW_UP_DEPTH:
            yield AnswerSavedEvent()
            yield TheoryEvaluationPersistenceService.advance_without_evaluation(
                interview_id=interview_id,
                question_id=ctx.question_id,
                round_num=ctx.round_num,
                order=ctx.order,
            )
            TheorySubmissionService._schedule_last_follow_up_evaluation(
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
            TheoryEvaluatorService.evaluate_submission(
                provider=provider,
                locale=ctx.locale,
                answer_round=ctx.round_num,
                question_text=ctx.question_text,
                question_code=ctx.question_code,
                initial_question_text=ctx.initial_question_text,
                initial_answer_text=ctx.initial_answer_text,
                expected_points=ctx.expected_points,
                answer_text=ctx.answer_text,
            )
        )

        yield TheoryEvaluationPersistenceService.persist(
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

        Args:
            interview_id: The session UUID.
            question_id: The question ID.
            wav_bytes: Canonical mono 16 kHz PCM WAV bytes.
            provider: AI provider for multimodal evaluation.
            transcriber: Loaded speech transcriber for transcript persistence.

        Yields:
            Semantic events for HTTP NDJSON or WebSocket delivery.
        """
        TheorySubmissionService.require_audio_answer_enabled()
        validate_wav_bytes(wav_bytes)

        ctx: TheorySubmissionContext | None = None
        async for item in TheorySubmissionService._open_submission(
            interview_id, question_id, ""
        ):
            if isinstance(item, TheorySubmissionContext):
                ctx = item
                break
            yield item
        if ctx is None:
            return

        yield AnswerSavedEvent()

        if ctx.round_num >= TheoryEvaluatorService.MAX_FOLLOW_UP_DEPTH:
            yield TheoryEvaluationPersistenceService.advance_without_evaluation(
                interview_id=interview_id,
                question_id=ctx.question_id,
                round_num=ctx.round_num,
                order=ctx.order,
            )
            transcript_task = asyncio.create_task(
                TheorySubmissionService._transcribe_and_persist(
                    interview_id=interview_id,
                    question_id=ctx.question_id,
                    round_num=ctx.round_num,
                    wav_bytes=wav_bytes,
                    transcriber=transcriber,
                    locale=ctx.locale,
                ),
                name=f"audio-transcript-{interview_id}-{ctx.question_id}-r{ctx.round_num}",
            )
            TheorySubmissionService._schedule_last_follow_up_evaluation(
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
            TheorySubmissionService._transcribe_and_persist(
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
            TheoryEvaluatorService.evaluate_submission(
                provider=provider,
                locale=ctx.locale,
                answer_round=ctx.round_num,
                question_text=ctx.question_text,
                question_code=ctx.question_code,
                initial_question_text=ctx.initial_question_text,
                initial_answer_text=ctx.initial_answer_text,
                expected_points=ctx.expected_points,
                audio_wav=wav_bytes,
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

        yield TheoryEvaluationPersistenceService.persist(
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
            async for event in TheorySubmissionService.stream_answer_submission(
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
            async for event in TheorySubmissionService.stream_audio_answer_submission(
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
            round_num: The task round that expired.

        Returns:
            Semantic events in delivery order.
        """
        return [
            event
            async for event in TheorySubmissionService.stream_timeout_submission(
                interview_id=interview_id,
                question_id=question_id,
                round_num=round_num,
            )
        ]
