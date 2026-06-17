# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket message handling for coding sessions."""

from collections.abc import AsyncIterator
import logging
from typing import Any

from app.ai.base import AIProvider
from app.coding.api.errors import coding_ws_error_payload
from app.coding.api.ws_protocol import coding_event_to_message
from app.coding.domain.exceptions import CodingDomainError
from app.coding.services.submission import CodingSubmissionService
from app.interview.domain.exceptions import InterviewDomainError
from app.interview.services.ai_errors import ai_error_message_for_client

logger = logging.getLogger(__name__)


class CodingWebSocketService:
    """Translate client coding WebSocket messages into server payloads."""

    @staticmethod
    async def iter_responses(
        raw: dict[str, Any],
        *,
        interview_id: str,
        provider: AIProvider,
        submission_service: CodingSubmissionService,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle one client message and yield JSON payloads for the socket.

        Args:
            raw: Parsed client JSON message.
            interview_id: Interview session UUID.
            provider: AI provider for coding evaluation.
            submission_service: Request-scoped coding submission service.

        Yields:
            WebSocket message dicts to send to the client.
        """
        msg_type = raw.get("type")
        if msg_type == "submit":
            async for message in CodingWebSocketService._handle_submit(
                raw,
                interview_id=interview_id,
                provider=provider,
                submission_service=submission_service,
            ):
                yield message
            return

        if msg_type == "timeout":
            async for message in CodingWebSocketService._handle_timeout(
                raw,
                interview_id=interview_id,
                submission_service=submission_service,
            ):
                yield message
            return

        yield {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        }

    @staticmethod
    async def _handle_submit(
        raw: dict[str, Any],
        *,
        interview_id: str,
        provider: AIProvider,
        submission_service: CodingSubmissionService,
    ) -> AsyncIterator[dict[str, Any]]:
        task_id = str(raw.get("task_id", "")).strip()
        source_code = str(raw.get("source_code", ""))
        if not task_id or not source_code:
            yield {
                "type": "error",
                "message": "Both task_id and source_code are required",
            }
            return

        try:
            async for event in submission_service.stream_submit(
                interview_id=interview_id,
                task_id=task_id,
                source_code=source_code,
                provider=provider,
            ):
                yield coding_event_to_message(event)
        except (InterviewDomainError, CodingDomainError) as exc:
            yield coding_ws_error_payload(exc)
        except Exception as exc:
            logger.exception("Coding submit failed for interview %s", interview_id)
            yield {
                "type": "error",
                "message": ai_error_message_for_client(exc),
            }

    @staticmethod
    async def _handle_timeout(
        raw: dict[str, Any],
        *,
        interview_id: str,
        submission_service: CodingSubmissionService,
    ) -> AsyncIterator[dict[str, Any]]:
        task_id = str(raw.get("task_id") or raw.get("question_id") or "").strip()
        round_num = raw.get("round")
        if not task_id or round_num is None:
            yield {"type": "error", "message": "Both task_id and round are required"}
            return

        try:
            async for event in submission_service.stream_timeout_submission(
                interview_id=interview_id,
                task_id=task_id,
                round_num=int(round_num),
            ):
                yield coding_event_to_message(event)
        except (InterviewDomainError, CodingDomainError) as exc:
            yield coding_ws_error_payload(exc)
        except Exception as exc:
            logger.exception("Coding timeout failed for interview %s", interview_id)
            yield {
                "type": "error",
                "message": ai_error_message_for_client(exc),
            }
