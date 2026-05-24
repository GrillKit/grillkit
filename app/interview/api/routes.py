# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides the interview page (HTTP GET) and a WebSocket
endpoint for real-time answers and completion. Business logic is
delegated to the service layer.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.interview.api.deps import (
    AIProviderDep,
    AnswerProcessingServiceDep,
    InterviewCompletionServiceDep,
    InterviewQueryDep,
)
from app.interview.api.errors import http_exception_from_domain_error, ws_error_payload
from app.interview.api.ws_protocol import event_to_message, events_to_messages
from app.interview.domain.selection import get_interview_selection
from app.interview.services.dashboard import DashboardBuilder
from app.platform.api.deps import ConfigServiceDep
from app.question_voice.api.audio import get_question_audio_path
from app.question_voice.api.page_context import build_question_voice_page_context
from app.question_voice.domain.tts_exceptions import (
    QuestionVoiceDisabledError,
    QuestionVoiceSynthesisError,
)
from app.shared.domain.exceptions import InterviewDomainError
from app.shared.domain.locales import (
    SUPPORTED_LOCALES,
    TIMEOUT_CHAT_LABELS,
    localized_string,
)
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.api.page_context import build_speech_model_page_context
from app.speech.api.preload import preload_whisper_for_active_interview
from app.templating import templates

router = APIRouter(prefix="/interview", tags=["interview"])

logger = logging.getLogger(__name__)


async def _safe_send_json(websocket: WebSocket, message: dict[str, Any]) -> bool:
    """Send a JSON message, returning False if the client already disconnected.

    Args:
        websocket: Active interview WebSocket.
        message: Payload to send.

    Returns:
        True if the message was sent, False if the socket is closed.
    """
    try:
        await websocket.send_json(message)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


def _ai_error_message(exc: Exception) -> str:
    """Turn provider failures into a short WebSocket error for the client.

    Args:
        exc: Exception raised during AI evaluation.

    Returns:
        User-facing error message.
    """
    text = str(exc)
    if "not found" in text.lower() and "model" in text.lower():
        return (
            "AI model is not available on the configured endpoint. "
            "Open /config and verify the model name and provider settings."
        )
    if "timed out" in text.lower() or "timeout" in text.lower():
        return (
            "AI evaluation timed out. The model may still be loading — "
            "wait and try again, or increase the timeout on /config."
        )
    return f"AI evaluation failed: {text}"


@router.get("/{interview_id}", response_class=HTMLResponse)
async def interview_page(
    request: Request,
    interview_id: str,
    interview_query: InterviewQueryDep,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> Response:
    """View an interview session.

    Loads the session with all answers. Active sessions show the
    current unanswered question; completed sessions show the full history.

    Args:
        request: FastAPI request object.
        interview_id: The session UUID.
        interview_query: Interview read service.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML response with interview view, or redirect if not found.
    """
    interview = interview_query.get_interview(interview_id)
    if not interview:
        return RedirectResponse(url="/", status_code=303)

    interview_status = interview.status
    if interview_status == "active":
        interview_query.ensure_current_round_started(interview_id)
        reloaded = interview_query.get_interview(interview_id)
        if reloaded is not None:
            interview = reloaded

    current_question = interview_query.get_current_unanswered(interview)
    question_timer_enabled = interview.question_time_limit_seconds is not None
    timer_remaining_seconds = (
        interview_query.timer_remaining_for_interview(interview)
        if question_timer_enabled
        else None
    )
    current_round = current_question.round if current_question else 0
    overall_feedback_data = DashboardBuilder.parse_overall_feedback(interview)
    max_score = DashboardBuilder.compute_max_score(interview)
    config = config_service.get_config()
    await preload_whisper_for_active_interview(
        request.app,
        config,
        interview_active=interview_status == "active",
    )

    selection = get_interview_selection(interview)
    selection_lines = DashboardBuilder.selection_summary_lines(selection)
    interview_title = DashboardBuilder.interview_display_title(interview)

    voice_ctx = await build_question_voice_page_context(config)
    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "interview": interview,
            "interview_title": interview_title,
            "selection_lines": selection_lines,
            "answers": interview.answers,
            "current_question": current_question,
            "current_answer_id": current_question.id if current_question else None,
            "question_voice_enabled": bool(config and config.question_voice_enabled),
            "overall_feedback": overall_feedback_data,
            "max_score": max_score,
            "locale_label": SUPPORTED_LOCALES.get(interview.locale, interview.locale),
            "question_timer_enabled": question_timer_enabled,
            "question_time_limit_seconds": interview.question_time_limit_seconds,
            "timer_remaining_seconds": timer_remaining_seconds,
            "current_round": current_round,
            "timeout_chat_label": localized_string(
                interview.locale, TIMEOUT_CHAT_LABELS
            ),
            "llm_request_timeout_seconds": int(config.timeout) if config else 60,
            **build_speech_model_page_context(config, whisper_model_service),
            **voice_ctx,
        },
    )


@router.get("/{interview_id}/question-audio")
async def question_audio(
    interview_id: str,
    answer_id: int | None = None,
) -> FileResponse:
    """Stream WAV audio for the current or specified unanswered question.

    Args:
        interview_id: Interview session UUID.
        answer_id: Optional answer row id; defaults to the first unanswered question.

    Returns:
        ``audio/wav`` file from cache or Piper synthesis.

    Raises:
        HTTPException: When voice is disabled, the session is invalid, or TTS fails.
    """
    try:
        path = await get_question_audio_path(interview_id, answer_id)
    except QuestionVoiceDisabledError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except QuestionVoiceSynthesisError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InterviewDomainError as exc:
        raise http_exception_from_domain_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(path, media_type="audio/wav", filename="question.wav")


@router.websocket("/{interview_id}/ws")
async def interview_ws(
    websocket: WebSocket,
    interview_id: str,
    interview_query: InterviewQueryDep,
    answer_processing: AnswerProcessingServiceDep,
    interview_completion: InterviewCompletionServiceDep,
    provider: AIProviderDep,
) -> None:
    """WebSocket endpoint for real-time interview interaction.

    Protocol (JSON messages):

    **Client → Server:**
    - ``{"type":"answer","question_id":"...","answer_text":"..."}``
    - ``{"type":"timeout","question_id":"...","round":N}``
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
        provider: AI provider for answer and session evaluation.
    """
    await websocket.accept()

    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except RuntimeError:
                break
            msg_type = raw.get("type")

            if msg_type == "answer":
                question_id = raw.get("question_id", "")
                answer_text = raw.get("answer_text", "")

                if not question_id or not answer_text:
                    await _safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": (
                                "Both question_id and answer_text are required"
                            ),
                        },
                    )
                    continue
                try:
                    async for event in answer_processing.stream_answer_submission(
                        interview_id=interview_id,
                        question_id=question_id,
                        answer_text=answer_text,
                        provider=provider,
                    ):
                        if not await _safe_send_json(
                            websocket, event_to_message(event)
                        ):
                            break
                except InterviewDomainError as e:
                    await _safe_send_json(websocket, ws_error_payload(e))
                except Exception as e:
                    logger.exception(
                        "WebSocket AI evaluation failed for session %s",
                        interview_id,
                    )
                    if not await _safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": _ai_error_message(e),
                        },
                    ):
                        break

            elif msg_type == "timeout":
                question_id = raw.get("question_id", "")
                round_num = raw.get("round")
                if not question_id or round_num is None:
                    await _safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": "Both question_id and round are required",
                        },
                    )
                    continue
                try:
                    async for event in answer_processing.stream_timeout_submission(
                        interview_id=interview_id,
                        question_id=question_id,
                        round_num=int(round_num),
                    ):
                        if not await _safe_send_json(
                            websocket, event_to_message(event)
                        ):
                            break
                except InterviewDomainError as e:
                    await _safe_send_json(websocket, ws_error_payload(e))
                except Exception as e:
                    logger.exception(
                        "WebSocket timeout failed for session %s",
                        interview_id,
                    )
                    await _safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": f"Timeout processing failed: {e}",
                        },
                    )

            elif msg_type == "ping":
                try:
                    interview = interview_query.get_interview(interview_id)
                    status = interview.status if interview else "not_found"
                    await _safe_send_json(websocket, {"type": "pong", "status": status})
                except Exception as e:
                    logger.warning("Ping failed for session %s: %s", interview_id, e)
                    await _safe_send_json(
                        websocket, {"type": "pong", "status": "error"}
                    )

            elif msg_type == "complete":
                try:
                    events = await interview_completion.complete_interview(
                        interview_id=interview_id,
                        provider=provider,
                    )
                    for message in events_to_messages(events):
                        if not await _safe_send_json(websocket, message):
                            break
                except InterviewDomainError as e:
                    await _safe_send_json(websocket, ws_error_payload(e))
                except Exception as e:
                    logger.exception(
                        "WebSocket session completion failed for session %s",
                        interview_id,
                    )
                    if not await _safe_send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": _ai_error_message(e),
                        },
                    ):
                        break
            else:
                await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    },
                )
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for session %s", interview_id)
    except RuntimeError:
        logger.debug("WebSocket closed for session %s", interview_id)
