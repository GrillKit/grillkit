# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket endpoint for interview answer dictation."""

import contextlib
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.interview.api.deps import InterviewQueryDep
from app.interview.domain.progress import require_active
from app.shared.domain.exceptions import InterviewNotActiveError
from app.speech.api.dictation_protocol import (
    DICTATION_CLIENT_START,
    DICTATION_CLIENT_STOP,
    DICTATION_SERVER_ERROR,
    DICTATION_SERVER_FINAL,
    DICTATION_SERVER_READY,
    dictation_message,
)
from app.speech.services.dictation import DictationSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])


async def _reject_dictation(websocket: WebSocket, message: str) -> None:
    """Accept, send an error JSON message, and close the dictation WebSocket.

    Args:
        websocket: Connection to close.
        message: User-facing error text.
    """
    await websocket.accept()
    await websocket.send_json(
        dictation_message(DICTATION_SERVER_ERROR, message=message)
    )
    await websocket.close(code=1008, reason=message[:120])


@router.websocket("/{interview_id}/dictation")
async def interview_dictation_ws(
    websocket: WebSocket,
    interview_id: str,
    interview_query: InterviewQueryDep,
) -> None:
    """Stream PCM audio and return a final transcript for the answer field.

    Separate from ``/{interview_id}/ws`` (answers and AI evaluation).

    **Client → server (text JSON):**
    - ``{"type":"start"}`` — begin a new dictation session
    - ``{"type":"stop"}`` — finalize and close

    **Client → server (binary):** 16-bit LE mono PCM, 16 kHz

    **Server → client:**
    - ``{"type":"ready"}`` — session initialized
    - ``{"type":"final","text":"..."}`` — final transcript (after ``stop``)
    - ``{"type":"error","message":"..."}`` — failure; connection closes

    Args:
        websocket: Dictation WebSocket connection.
        interview_id: Interview session UUID.
        interview_query: Interview read service.
    """
    interview = interview_query.get_interview(interview_id)
    if interview is None:
        await _reject_dictation(websocket, "Interview not found")
        return

    try:
        require_active(interview)
    except InterviewNotActiveError:
        await _reject_dictation(websocket, "Interview is not active")
        return

    transcriber = getattr(websocket.app.state, "speech_transcriber", None)
    if transcriber is None:
        await _reject_dictation(
            websocket,
            "Speech model is not loaded. Download it in Configuration.",
        )
        return

    await websocket.accept()
    session: DictationSession | None = None

    try:
        while True:
            incoming = await websocket.receive()
            if incoming.get("type") == "websocket.disconnect":
                break

            if "text" in incoming:
                try:
                    payload = json.loads(incoming["text"])
                except json.JSONDecodeError:
                    await websocket.send_json(
                        dictation_message(
                            DICTATION_SERVER_ERROR,
                            message="Invalid JSON message",
                        )
                    )
                    continue

                msg_type = payload.get("type")
                if msg_type == DICTATION_CLIENT_START:
                    session = DictationSession()
                    await websocket.send_json(dictation_message(DICTATION_SERVER_READY))
                elif msg_type == DICTATION_CLIENT_STOP:
                    if session is None:
                        await websocket.send_json(
                            dictation_message(
                                DICTATION_SERVER_ERROR,
                                message="Send start before stop",
                            )
                        )
                        continue
                    final_text = await session.finalize(transcriber, interview.locale)
                    await websocket.send_json(
                        dictation_message(
                            DICTATION_SERVER_FINAL,
                            text=final_text,
                        )
                    )
                    break
                else:
                    await websocket.send_json(
                        dictation_message(
                            DICTATION_SERVER_ERROR,
                            message=f"Unknown message type: {msg_type}",
                        )
                    )
                continue

            if "bytes" in incoming:
                if session is None:
                    await websocket.send_json(
                        dictation_message(
                            DICTATION_SERVER_ERROR,
                            message="Send start before audio chunks",
                        )
                    )
                    continue
                session.append_pcm(incoming["bytes"])
    except WebSocketDisconnect:
        logger.debug("Dictation WebSocket disconnected for session %s", interview_id)
    except Exception as exc:
        logger.exception("Dictation failed for session %s", interview_id)
        with contextlib.suppress(Exception):
            await websocket.send_json(
                dictation_message(
                    DICTATION_SERVER_ERROR,
                    message=f"Dictation failed: {exc}",
                )
            )
