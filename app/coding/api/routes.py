# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section HTTP and WebSocket transport."""

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.coding.api.errors import http_exception_from_coding_error
from app.coding.api.ws_session import CodingWebSocketService
from app.coding.domain.exceptions import CodingDomainError
from app.coding.schemas.coding import (
    CodingRunRequest,
    CodingRunResponse,
    coding_state_to_dict,
    domain_run_attempt_to_read,
    run_attempt_to_response,
)
from app.coding.services.run_execution import CodingRunExecutionService
from app.interview.api.deps import (
    AIProviderDep,
    CodingStateServiceDep,
    CodingSubmissionServiceDep,
)
from app.interview.domain.exceptions import InterviewDomainError

router = APIRouter(prefix="/interview", tags=["coding"])

logger = logging.getLogger(__name__)


async def _safe_send_json(websocket: WebSocket, message: dict[str, Any]) -> bool:
    """Send a JSON message, returning False if the client already disconnected.

    Args:
        websocket: Active coding WebSocket.
        message: Payload to send.

    Returns:
        True if the message was sent, False if the socket is closed.
    """
    try:
        await websocket.send_json(message)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


@router.post("/{interview_id}/coding/run", response_model=CodingRunResponse)
async def coding_run(
    interview_id: str,
    body: CodingRunRequest,
) -> CodingRunResponse:
    """Execute public tests for the active coding task and persist the attempt.

    Args:
        interview_id: Interview session UUID.
        body: Task ID and current editor contents.

    Returns:
        Mirror of the persisted Run attempt.

    Raises:
        HTTPException: On validation, domain, or rate-limit errors.
    """
    try:
        attempt = await CodingRunExecutionService.run_and_persist(
            interview_id=interview_id,
            task_id=body.task_id,
            source_code=body.source_code,
        )
    except (InterviewDomainError, CodingDomainError) as exc:
        raise http_exception_from_coding_error(exc) from exc
    return run_attempt_to_response(domain_run_attempt_to_read(attempt))


@router.get("/{interview_id}/coding/state")
async def coding_state(
    interview_id: str,
    service: CodingStateServiceDep,
) -> JSONResponse:
    """Return coding session progress and Run history for the active task.

    Args:
        interview_id: Interview session UUID.

    Returns:
        JSON read model for the coding panel.

    Raises:
        HTTPException: When the coding section does not exist.
    """
    try:
        state = service.get_state(interview_id)
    except CodingDomainError as exc:
        raise http_exception_from_coding_error(exc) from exc
    return JSONResponse(coding_state_to_dict(state))


@router.websocket("/{interview_id}/coding/ws")
async def coding_ws(
    websocket: WebSocket,
    interview_id: str,
    provider: AIProviderDep,
    submission_service: CodingSubmissionServiceDep,
) -> None:
    """WebSocket endpoint for coding task submit and feedback.

    Args:
        websocket: The WebSocket connection.
        interview_id: The session UUID.
        provider: AI provider for coding evaluation.
    """
    await websocket.accept()
    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except RuntimeError:
                break

            async for message in CodingWebSocketService.iter_responses(
                raw,
                interview_id=interview_id,
                provider=provider,
                submission_service=submission_service,
            ):
                if not await _safe_send_json(websocket, message):
                    break
    except WebSocketDisconnect:
        logger.debug("Coding WebSocket disconnected for session %s", interview_id)
    except RuntimeError:
        logger.debug("Coding WebSocket closed for session %s", interview_id)
