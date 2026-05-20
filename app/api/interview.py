# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides the interview page (HTTP GET) and a WebSocket
endpoint for real-time answers and completion. Business logic is
delegated to the service layer.
"""

import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.api.deps import (
    AnswerProcessingServiceDep,
    InterviewCompletionServiceDep,
    InterviewQueryDep,
)
from app.api.interview_errors import ws_error_payload
from app.api.ws_protocol import events_to_messages
from app.domain.exceptions import InterviewDomainError
from app.domain.locales import SUPPORTED_LOCALES
from app.templating import templates

router = APIRouter(prefix="/interview", tags=["interview"])

logger = logging.getLogger(__name__)


@router.get("/{interview_id}", response_class=HTMLResponse)
async def interview_page(
    request: Request,
    interview_id: str,
    interview_query: InterviewQueryDep,
) -> Response:
    """View an interview session.

    Loads the session with all answers. Active sessions show the
    current unanswered question; completed sessions show the full history.

    Args:
        request: FastAPI request object.
        interview_id: The session UUID.
        interview_query: Interview read service.

    Returns:
        HTML response with interview view, or redirect if not found.
    """
    interview = interview_query.get_interview(interview_id)
    if not interview:
        return RedirectResponse(url="/", status_code=303)

    current_question = interview_query.get_current_unanswered(interview)
    overall_feedback_data = interview_query.parse_overall_feedback(interview)
    max_score = interview_query.compute_max_score(interview)

    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "interview": interview,
            "answers": interview.answers,
            "current_question": current_question,
            "overall_feedback": overall_feedback_data,
            "max_score": max_score,
            "locale_label": SUPPORTED_LOCALES.get(interview.locale, interview.locale),
        },
    )


@router.websocket("/{interview_id}/ws")
async def interview_ws(
    websocket: WebSocket,
    interview_id: str,
    interview_query: InterviewQueryDep,
    answer_processing: AnswerProcessingServiceDep,
    interview_completion: InterviewCompletionServiceDep,
) -> None:
    """WebSocket endpoint for real-time interview interaction.

    Protocol (JSON messages):

    **Client → Server:**
    - ``{"type":"answer","question_id":"...","answer_text":"..."}``
    - ``{"type":"complete"}``

    **Server → Client:**
    - ``{"type":"saved"}`` — answer persisted
    - ``{"type":"evaluating"}`` — AI is evaluating
    - ``{"type":"feedback",...}`` — follow-up or next question navigation
    - ``{"type":"interview_completed","overall_feedback":{...},"score":N}``
    - ``{"type":"error","message":"..."}``

    Args:
        websocket: The WebSocket connection.
        interview_id: The session UUID.
        interview_query: Interview read service.
        answer_processing: Answer processing service.
        interview_completion: Interview completion service.
    """
    await websocket.accept()

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
                            "message": (
                                "Both question_id and answer_text are required"
                            ),
                        }
                    )
                    continue
                try:
                    events = await answer_processing.process_answer_submission(
                        interview_id=interview_id,
                        question_id=question_id,
                        answer_text=answer_text,
                    )
                    for message in events_to_messages(events):
                        await websocket.send_json(message)
                except InterviewDomainError as e:
                    await websocket.send_json(ws_error_payload(e))
                except Exception as e:
                    logger.exception(
                        "WebSocket AI evaluation failed for session %s",
                        interview_id,
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"AI evaluation failed: {e}",
                        }
                    )

            elif msg_type == "ping":
                try:
                    interview = interview_query.get_interview(interview_id)
                    status = interview.status if interview else "not_found"
                    await websocket.send_json({"type": "pong", "status": status})
                except Exception as e:
                    logger.warning("Ping failed for session %s: %s", interview_id, e)
                    await websocket.send_json({"type": "pong", "status": "error"})

            elif msg_type == "complete":
                try:
                    events = await interview_completion.complete_interview(
                        interview_id=interview_id,
                    )
                    for message in events_to_messages(events):
                        await websocket.send_json(message)
                except InterviewDomainError as e:
                    await websocket.send_json(ws_error_payload(e))
                except Exception as e:
                    logger.exception(
                        "WebSocket session completion failed for session %s",
                        interview_id,
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Session evaluation failed: {e}",
                        }
                    )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    }
                )
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for session %s", interview_id)
