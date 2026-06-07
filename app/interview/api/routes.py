# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides the interview page (HTTP GET) and a WebSocket
endpoint for real-time answers and completion. Business logic is
delegated to the service layer.
"""

import logging
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)

from app.interview.api.audio_answer import InterviewAudioAnswerAdapter
from app.interview.api.deps import (
    AIProviderDep,
    InterviewCompletionServiceDep,
    InterviewQueryDep,
    SpeechTranscriberDep,
)
from app.interview.api.errors import http_exception_from_domain_error
from app.interview.api.ws_session import InterviewWebSocketService
from app.interview.domain.exceptions import InterviewDomainError
from app.interview.services.page import InterviewPageService
from app.platform.api.deps import ConfigServiceDep
from app.platform.services.speech_runtime import SpeechRuntimeCoordinator
from app.question_voice.services.question_audio import get_question_audio_path
from app.question_voice.services.tts_exceptions import (
    QuestionVoiceDisabledError,
    QuestionVoiceSynthesisError,
)
from app.speech.api.deps import WhisperModelServiceDep
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


@router.get("/{interview_id}", response_class=HTMLResponse)
async def interview_page(
    request: Request,
    interview_id: str,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> Response:
    """View an interview session.

    Loads the session with all answers. Active sessions show the
    current unanswered question; completed sessions show the full history.

    Args:
        request: FastAPI request object.
        interview_id: The session UUID.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML response with interview view, or redirect if not found.
    """
    config = config_service.get_config()
    page = await InterviewPageService.prepare_page(
        interview_id,
        config=config,
        whisper_model_service=whisper_model_service,
    )
    if page.redirect_url is not None:
        return RedirectResponse(url=page.redirect_url, status_code=303)

    await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
        request.app,
        config,
        interview_active=page.interview_active,
    )
    return templates.TemplateResponse(
        request,
        "interview.html",
        page.template_context or {},
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


@router.post("/{interview_id}/audio-answer")
async def submit_audio_answer(
    interview_id: str,
    provider: AIProviderDep,
    transcriber: SpeechTranscriberDep,
    question_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> StreamingResponse:
    """Submit a spoken answer and stream NDJSON evaluation events.

    Multipart form fields:
    - ``question_id`` — question being answered
    - ``file`` — canonical mono 16 kHz PCM WAV bytes

    Response lines use the same event shapes as the interview WebSocket
    (``saved``, ``evaluating``, ``transcript``, ``feedback``, ``error``).

    Args:
        interview_id: Interview session UUID.
        provider: AI provider for multimodal evaluation.
        transcriber: Loaded Whisper transcriber for audio transcription.
        question_id: Question ID from the active answer row.
        file: Uploaded WAV audio answer.

    Returns:
        NDJSON stream of server events.

    Raises:
        HTTPException: When required fields are missing or WAV validation fails.
    """
    wav_bytes = await file.read()
    try:
        normalized_question_id = InterviewAudioAnswerAdapter.parse_submission(
            question_id=question_id,
            wav_bytes=wav_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        InterviewAudioAnswerAdapter.stream_ndjson_lines(
            interview_id=interview_id,
            question_id=normalized_question_id,
            wav_bytes=wav_bytes,
            provider=provider,
            transcriber=transcriber,
        ),
        media_type="application/x-ndjson",
    )


@router.websocket("/{interview_id}/ws")
async def interview_ws(
    websocket: WebSocket,
    interview_id: str,
    interview_query: InterviewQueryDep,
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

            async for message in InterviewWebSocketService.iter_responses(
                raw,
                interview_id=interview_id,
                provider=provider,
                interview_completion=interview_completion,
                interview_query=interview_query,
            ):
                if not await _safe_send_json(websocket, message):
                    break
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for session %s", interview_id)
    except RuntimeError:
        logger.debug("WebSocket closed for session %s", interview_id)
