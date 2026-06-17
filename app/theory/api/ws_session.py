# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket message handling for theory sessions."""

from collections.abc import AsyncIterator
import logging
from typing import Any

from app.ai.base import AIProvider
from app.interview.domain.exceptions import InterviewDomainError
from app.interview.services.ai_errors import ai_error_message_for_client
from app.interview.services.completion import SessionCompletionService
from app.interview.services.query import InterviewQuery
from app.theory.api.ws_protocol import (
    domain_error_to_wire,
    event_to_message,
    events_to_messages,
)
from app.theory.domain.exceptions import TheoryDomainError
from app.theory.services.submission import TheorySubmissionService

logger = logging.getLogger(__name__)


class TheoryWebSocketService:
    """Translate client WebSocket messages into server response payloads."""

    @staticmethod
    async def iter_responses(
        raw: dict[str, Any],
        *,
        interview_id: str,
        provider: AIProvider,
        submission_service: TheorySubmissionService,
        session_completion: SessionCompletionService,
        interview_query: InterviewQuery,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle one client message and yield JSON payloads for the socket.

        Args:
            raw: Parsed client JSON message.
            interview_id: Interview session UUID.
            provider: AI provider for answer and session evaluation.
            submission_service: Request-scoped theory submission service.
            session_completion: Request-scoped session completion service.
            interview_query: Request-scoped interview read helper.

        Yields:
            WebSocket message dicts to send to the client.
        """
        msg_type = raw.get("type")

        if msg_type == "answer":
            async for message in TheoryWebSocketService._handle_answer(
                raw,
                interview_id=interview_id,
                provider=provider,
                submission_service=submission_service,
            ):
                yield message
            return

        if msg_type == "timeout":
            async for message in TheoryWebSocketService._handle_timeout(
                raw,
                interview_id=interview_id,
                submission_service=submission_service,
            ):
                yield message
            return

        if msg_type == "ping":
            yield TheoryWebSocketService._handle_ping(
                interview_id,
                interview_query=interview_query,
            )
            return

        if msg_type == "complete":
            async for message in TheoryWebSocketService._handle_complete(
                interview_id=interview_id,
                provider=provider,
                session_completion=session_completion,
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
        submission_service: TheorySubmissionService,
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
            async for event in submission_service.stream_answer_submission(
                interview_id=interview_id,
                question_id=question_id,
                answer_text=answer_text,
                provider=provider,
            ):
                yield event_to_message(event)
        except (InterviewDomainError, TheoryDomainError) as exc:
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
        submission_service: TheorySubmissionService,
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
            async for event in submission_service.stream_timeout_submission(
                interview_id=interview_id,
                question_id=question_id,
                round_num=int(round_num),
            ):
                yield event_to_message(event)
        except (InterviewDomainError, TheoryDomainError) as exc:
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
        interview_query: InterviewQuery,
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
        session_completion: SessionCompletionService,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            events = await session_completion.complete_session(
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
