# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""HTTP audio-answer transport adapter for theory sessions."""

from collections.abc import AsyncIterator
import json
import logging

from app.ai.base import AIProvider
from app.ai.speech_transcriber import SpeechTranscriber
from app.interview.domain.exceptions import InterviewDomainError
from app.interview.services.ai_errors import ai_error_message_for_client
from app.shared.infrastructure.audio_wav import validate_wav_bytes
from app.theory.api.ws_protocol import domain_error_to_wire, event_to_message
from app.theory.domain.exceptions import TheoryDomainError
from app.theory.services.submission import TheorySubmissionService

logger = logging.getLogger(__name__)


class TheoryAudioAnswerAdapter:
    """Validate multipart input and stream NDJSON wire payloads."""

    @staticmethod
    def parse_submission(*, question_id: str, wav_bytes: bytes) -> str:
        """Validate form fields and WAV payload before submission.

        Args:
            question_id: Question ID from the active task row.
            wav_bytes: Uploaded WAV audio bytes.

        Returns:
            Normalized question ID.

        Raises:
            ValueError: When required fields are missing or invalid.
        """
        normalized_question_id = question_id.strip()
        if not normalized_question_id:
            raise ValueError("question_id is required")
        if not wav_bytes:
            raise ValueError("Audio file is required")
        TheorySubmissionService.require_audio_answer_enabled()
        validate_wav_bytes(wav_bytes)
        return normalized_question_id

    @staticmethod
    async def stream_ndjson_lines(
        *,
        interview_id: str,
        question_id: str,
        wav_bytes: bytes,
        provider: AIProvider,
        transcriber: SpeechTranscriber,
    ) -> AsyncIterator[str]:
        """Map audio answer service events to NDJSON response lines.

        Args:
            interview_id: Interview session UUID.
            question_id: Normalized question ID.
            wav_bytes: Validated WAV payload.
            provider: Configured AI provider.
            transcriber: Loaded speech transcriber.

        Yields:
            One JSON object per line for ``StreamingResponse``.
        """
        try:
            async for event in TheorySubmissionService.stream_audio_answer_submission(
                interview_id=interview_id,
                question_id=question_id,
                wav_bytes=wav_bytes,
                provider=provider,
                transcriber=transcriber,
            ):
                yield json.dumps(event_to_message(event)) + "\n"
        except (InterviewDomainError, TheoryDomainError) as exc:
            yield json.dumps(domain_error_to_wire(exc)) + "\n"
        except ValueError as exc:
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
        except Exception as exc:
            logger.exception(
                "Audio answer submission failed for session %s",
                interview_id,
            )
            yield (
                json.dumps(
                    {"type": "error", "message": ai_error_message_for_client(exc)}
                )
                + "\n"
            )
