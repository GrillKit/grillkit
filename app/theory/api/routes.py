# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section HTTP and WebSocket transport."""

import logging
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse

from app.interview.api.deps import (
    AIProviderDep,
    InterviewQueryDep,
    SessionCompletionServiceDep,
    SpeechTranscriberDep,
)
from app.theory.api.audio_answer import TheoryAudioAnswerAdapter
from app.theory.api.ws_session import TheoryWebSocketService

router = APIRouter(prefix="/interview", tags=["theory"])

logger = logging.getLogger(__name__)


async def _safe_send_json(websocket: WebSocket, message: dict[str, Any]) -> bool:
    """Send a JSON message, returning False if the client already disconnected.

    Args:
        websocket: Active theory WebSocket.
        message: Payload to send.

    Returns:
        True if the message was sent, False if the socket is closed.
    """
    try:
        await websocket.send_json(message)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


@router.post("/{interview_id}/theory/audio-answer")
async def submit_theory_audio_answer(
    interview_id: str,
    provider: AIProviderDep,
    transcriber: SpeechTranscriberDep,
    question_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> StreamingResponse:
    """Submit a spoken theory answer and stream NDJSON evaluation events.

    Args:
        interview_id: Interview session UUID.
        provider: AI provider for multimodal evaluation.
        transcriber: Loaded Whisper transcriber for audio transcription.
        question_id: Question ID from the active task row.
        file: Uploaded WAV audio answer.

    Returns:
        NDJSON stream of server events.

    Raises:
        HTTPException: When required fields are missing or WAV validation fails.
    """
    wav_bytes = await file.read()
    try:
        normalized_question_id = TheoryAudioAnswerAdapter.parse_submission(
            question_id=question_id,
            wav_bytes=wav_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        TheoryAudioAnswerAdapter.stream_ndjson_lines(
            interview_id=interview_id,
            question_id=normalized_question_id,
            wav_bytes=wav_bytes,
            provider=provider,
            transcriber=transcriber,
        ),
        media_type="application/x-ndjson",
    )


async def handle_theory_websocket(
    websocket: WebSocket,
    interview_id: str,
    interview_query: InterviewQueryDep,
    session_completion: SessionCompletionServiceDep,
    provider: AIProviderDep,
) -> None:
    """Run the theory WebSocket message loop until disconnect.

    Args:
        websocket: The WebSocket connection.
        interview_id: The session UUID.
        interview_query: Interview read service.
        session_completion: Session completion service.
        provider: AI provider for answer and session evaluation.
    """
    await websocket.accept()

    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except RuntimeError:
                break

            async for message in TheoryWebSocketService.iter_responses(
                raw,
                interview_id=interview_id,
                provider=provider,
                session_completion=session_completion,
                interview_query=interview_query,
            ):
                if not await _safe_send_json(websocket, message):
                    break
    except WebSocketDisconnect:
        logger.debug("Theory WebSocket disconnected for session %s", interview_id)
    except RuntimeError:
        logger.debug("Theory WebSocket closed for session %s", interview_id)


@router.websocket("/{interview_id}/theory/ws")
async def theory_ws(
    websocket: WebSocket,
    interview_id: str,
    interview_query: InterviewQueryDep,
    session_completion: SessionCompletionServiceDep,
    provider: AIProviderDep,
) -> None:
    """WebSocket endpoint for real-time theory task interaction.

    Args:
        websocket: The WebSocket connection.
        interview_id: The session UUID.
        interview_query: Interview read service.
        session_completion: Session completion service.
        provider: AI provider for answer and session evaluation.
    """
    await handle_theory_websocket(
        websocket,
        interview_id,
        interview_query,
        session_completion,
        provider,
    )
