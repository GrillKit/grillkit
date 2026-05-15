# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides HTTP endpoints for viewing and interacting
with interview sessions, as well as a WebSocket endpoint for
real-time interaction. All business logic is delegated to the
service layer.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import (
    APIRouter,
    Form,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..services.interview_session import InterviewSessionService

router = APIRouter(prefix="/interview", tags=["interview"])
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)


@router.get("/{session_id}", response_class=HTMLResponse)
async def interview_page(request: Request, session_id: str):
    """View an interview session.

    Loads the session with all answers. Active sessions show the
    current unanswered question; completed sessions show the full history.

    Args:
        request: FastAPI request object.
        session_id: The session UUID.

    Returns:
        HTML response with interview view, or redirect if not found.
    """
    session = InterviewSessionService.get_session(session_id)
    if not session:
        return RedirectResponse(url="/", status_code=303)

    # Find the first unanswered question
    current_question = None
    for answer in session.answers:
        if answer.answer_text is None:
            current_question = answer
            break

    # Parse overall_feedback JSON for the template
    overall_feedback_data = None
    if session.overall_feedback:
        try:
            overall_feedback_data = json.loads(session.overall_feedback)
        except json.JSONDecodeError:
            overall_feedback_data = {"overall_feedback": session.overall_feedback}

    # Calculate max possible score (5 per answered round, including follow-ups)
    answered_answers = [a for a in session.answers if a.answer_text is not None]
    max_score = len(answered_answers) * 5

    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "session": session,
            "answers": session.answers,
            "current_question": current_question,
            "overall_feedback": overall_feedback_data,
            "max_score": max_score,
        },
    )


@router.websocket("/{session_id}/ws")
async def interview_ws(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time interview interaction.

    Protocol (JSON messages):

    **Client → Server:**
    - ``{"type":"answer","question_id":"...","answer_text":"..."}``
    - ``{"type":"complete"}``

    **Server → Client:**
    - ``{"type":"saved"}`` — answer persisted
    - ``{"type":"evaluating"}`` — AI is evaluating
    - ``{"type":"feedback","score":N,"feedback":"...",...}`` — evaluation result
    - ``{"type":"session_completed","overall_feedback":{...},"score":N}``
    - ``{"type":"error","message":"..."}``

    Args:
        websocket: The WebSocket connection.
        session_id: The session UUID.
    """
    await websocket.accept()

    # Use an asyncio.Queue to buffer outgoing messages.
    # The service layer calls ws_send synchronously, but send_json is async.
    # A background task drains the queue, preserving message order and
    # preventing silent message loss on disconnect.
    send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def _send_worker():
        """Background task that drains send_queue and writes to WebSocket."""
        while True:
            data = await send_queue.get()
            try:
                await websocket.send_json(data)
            except Exception:
                logger.warning("WS send failed: %s", data.get("type", "unknown"))
                break

    send_task = asyncio.create_task(_send_worker())

    def ws_send(data: dict[str, Any]) -> None:
        """Synchronously enqueue a JSON message for WebSocket delivery."""
        send_queue.put_nowait(data)

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "answer":
                question_id = raw.get("question_id", "")
                answer_text = raw.get("answer_text", "")

                if not question_id or not answer_text:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Both question_id and answer_text are required",
                        }
                    )
                    continue

                try:
                    # Validate session is active
                    session = InterviewSessionService.get_session(session_id)
                    if not session:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Session not found",
                            }
                        )
                        continue
                    if session.status != "active":
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Cannot submit answer to a completed session",
                            }
                        )
                        continue

                    await InterviewSessionService.process_answer_submission(
                        session_id=session_id,
                        question_id=question_id,
                        answer_text=answer_text,
                        ws_send=ws_send,
                    )
                except ValueError as e:
                    ws_send({"type": "error", "message": str(e)})
                except Exception as e:
                    logger.exception(
                        "WebSocket AI evaluation failed for session %s", session_id
                    )
                    ws_send({"type": "error", "message": f"AI evaluation failed: {e}"})

            elif msg_type == "ping":
                # Client checks session status after reconnect
                try:
                    session = InterviewSessionService.get_session(session_id)
                    status = session.status if session else "not_found"
                    await websocket.send_json({"type": "pong", "status": status})
                except Exception as e:
                    logger.warning("Ping failed for session %s: %s", session_id, e)
                    await websocket.send_json({"type": "pong", "status": "error"})

            elif msg_type == "complete":
                try:
                    await InterviewSessionService.process_session_completion(
                        session_id=session_id,
                        ws_send=ws_send,
                    )
                except ValueError as e:
                    ws_send({"type": "error", "message": str(e)})
                except Exception as e:
                    logger.exception(
                        "WebSocket session completion failed for session %s", session_id
                    )
                    ws_send(
                        {"type": "error", "message": f"Session evaluation failed: {e}"}
                    )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    }
                )
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for session %s", session_id)
    finally:
        # Cancel the send worker so it doesn't outlive the connection
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task


@router.post("/{session_id}/answer", response_class=HTMLResponse)
async def submit_answer(
    request: Request,
    session_id: str,
    question_id: str = Form(...),
    answer_text: str = Form(...),
):
    """Submit an answer for the current question.

    Delegates to InterviewSessionService which handles saving,
    AI evaluation, and follow-up generation.

    Args:
        request: FastAPI request object.
        session_id: The session UUID.
        question_id: The question ID being answered.
        answer_text: The user's answer text.

    Returns:
        Redirect to the interview page.
    """
    # Validate session exists and is still active
    session = InterviewSessionService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Cannot submit answer to a completed session",
        )

    try:
        await InterviewSessionService.process_answer_submission(
            session_id=session_id,
            question_id=question_id,
            answer_text=answer_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to process answer for session %s", session_id)
        raise HTTPException(status_code=502, detail=f"AI evaluation failed: {e}") from e

    return RedirectResponse(
        url=f"/interview/{session_id}",
        status_code=303,
    )


@router.post("/{session_id}/complete", response_class=HTMLResponse)
async def complete_interview(request: Request, session_id: str):
    """Mark an interview session as completed.

    Delegates to InterviewSessionService which handles AI evaluation
    of the entire session and saves overall feedback.

    Args:
        request: FastAPI request object.
        session_id: The session UUID.

    Returns:
        Redirect to the interview page.
    """
    try:
        await InterviewSessionService.process_session_completion(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to complete session %s", session_id)
        raise HTTPException(
            status_code=502, detail=f"Session evaluation failed: {e}"
        ) from e

    return RedirectResponse(
        url=f"/interview/{session_id}",
        status_code=303,
    )
