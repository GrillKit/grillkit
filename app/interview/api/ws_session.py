# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket message handling for interview sessions."""

from collections.abc import AsyncIterator
import logging
from typing import Any

from app.ai.base import AIProvider
from app.interview.api.ws_protocol import (
    domain_error_to_wire,
    event_to_message,
    events_to_messages,
)
from app.interview.domain.exceptions import InterviewDomainError
from app.interview.services.ai_errors import ai_error_message_for_client
from app.interview.services.answer_processing import AnswerProcessingService
from app.interview.services.completion import InterviewCompletionService
from app.interview.services.query import InterviewQuery

logger = logging.getLogger(__name__)


class InterviewWebSocketService:
    """Translate client WebSocket messages into server response payloads."""

    @staticmethod
    async def iter_responses(
        raw: dict[str, Any],
        *,
        interview_id: str,
        provider: AIProvider,
        answer_processing: type[AnswerProcessingService] = AnswerProcessingService,
        interview_completion: type[
            InterviewCompletionService
        ] = InterviewCompletionService,
        interview_query: type[InterviewQuery] = InterviewQuery,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle one client message and yield JSON payloads for the socket.

        Args:
            raw: Parsed client JSON message.
            interview_id: Interview session UUID.
            provider: AI provider for answer and session evaluation.
            answer_processing: Answer processing service class.
            interview_completion: Session completion service class.
            interview_query: Interview read service class.

        Yields:
            WebSocket message dicts to send to the client.
        """
        msg_type = raw.get("type")

        if msg_type == "answer":
            async for message in InterviewWebSocketService._handle_answer(
                raw,
                interview_id=interview_id,
                provider=provider,
                answer_processing=answer_processing,
            ):
                yield message
            return

        if msg_type == "timeout":
            async for message in InterviewWebSocketService._handle_timeout(
                raw,
                interview_id=interview_id,
                answer_processing=answer_processing,
            ):
                yield message
            return

        if msg_type == "ping":
            yield InterviewWebSocketService._handle_ping(
                interview_id,
                interview_query=interview_query,
            )
            return

        if msg_type == "complete":
            async for message in InterviewWebSocketService._handle_complete(
                interview_id=interview_id,
                provider=provider,
                interview_completion=interview_completion,
            ):
                yield message
            return

        yield {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        }

    @staticmethod
    async def _handle_answer(
        raw: dict[str, Any],
        *,
        interview_id: str,
        provider: AIProvider,
        answer_processing: type[AnswerProcessingService],
    ) -> AsyncIterator[dict[str, Any]]:
        question_id = raw.get("question_id", "")
        answer_text = raw.get("answer_text", "")
        if not question_id or not answer_text:
            yield {
                "type": "error",
                "message": "Both question_id and answer_text are required",
            }
            return

        try:
            async for event in answer_processing.stream_answer_submission(
                interview_id=interview_id,
                question_id=question_id,
                answer_text=answer_text,
                provider=provider,
            ):
                yield event_to_message(event)
        except InterviewDomainError as exc:
            yield domain_error_to_wire(exc)
        except Exception as exc:
            logger.exception(
                "WebSocket AI evaluation failed for session %s",
                interview_id,
            )
            yield {
                "type": "error",
                "message": ai_error_message_for_client(exc),
            }

    @staticmethod
    async def _handle_timeout(
        raw: dict[str, Any],
        *,
        interview_id: str,
        answer_processing: type[AnswerProcessingService],
    ) -> AsyncIterator[dict[str, Any]]:
        question_id = raw.get("question_id", "")
        round_num = raw.get("round")
        if not question_id or round_num is None:
            yield {
                "type": "error",
                "message": "Both question_id and round are required",
            }
            return

        try:
            async for event in answer_processing.stream_timeout_submission(
                interview_id=interview_id,
                question_id=question_id,
                round_num=int(round_num),
            ):
                yield event_to_message(event)
        except InterviewDomainError as exc:
            yield domain_error_to_wire(exc)
        except Exception as exc:
            logger.exception(
                "WebSocket timeout failed for session %s",
                interview_id,
            )
            yield {
                "type": "error",
                "message": f"Timeout processing failed: {exc}",
            }

    @staticmethod
    def _handle_ping(
        interview_id: str,
        *,
        interview_query: type[InterviewQuery],
    ) -> dict[str, Any]:
        try:
            interview = interview_query.get_interview(interview_id)
            status = interview.status if interview else "not_found"
            return {"type": "pong", "status": status}
        except Exception as exc:
            logger.warning("Ping failed for session %s: %s", interview_id, exc)
            return {"type": "pong", "status": "error"}

    @staticmethod
    async def _handle_complete(
        *,
        interview_id: str,
        provider: AIProvider,
        interview_completion: type[InterviewCompletionService],
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            events = await interview_completion.complete_interview(
                interview_id=interview_id,
                provider=provider,
            )
            for message in events_to_messages(events):
                yield message
        except InterviewDomainError as exc:
            yield domain_error_to_wire(exc)
        except Exception as exc:
            logger.exception(
                "WebSocket session completion failed for session %s",
                interview_id,
            )
            yield {
                "type": "error",
                "message": ai_error_message_for_client(exc),
            }
