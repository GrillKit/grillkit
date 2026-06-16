# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides the interview page (HTTP GET). Business logic is
delegated to the service layer; theory transport lives under ``/theory/``.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.interview.api.deps import SessionPageServiceDep
from app.interview.api.errors import http_exception_from_domain_error
from app.interview.domain.exceptions import InterviewDomainError
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


def _interview_template_name(context: dict[str, object]) -> str:
    """Pick the interview page template for the active session phase.

    Args:
        context: Template context from ``SessionPageService``.

    Returns:
        Template path for theory or coding-focused rendering.
    """
    if context.get("active_phase") == "coding":
        return "coding_interview.html"
    return "interview.html"


@router.get("/{interview_id}", response_class=HTMLResponse)
async def interview_page(
    request: Request,
    interview_id: str,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
    page_service: SessionPageServiceDep,
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
    page = await page_service.prepare_page(
        interview_id,
        config=config,
        whisper_model_service=whisper_model_service,
    )
    if page.redirect_url is not None:
        return RedirectResponse(url=page.redirect_url, status_code=303)

    context = page.template_context or {}
    if context.get("interview", {}).get("status") == "completed":
        return RedirectResponse(
            url=f"/interview/{interview_id}/results",
            status_code=303,
        )

    await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
        request.app,
        config,
        interview_active=page.interview_active,
    )
    return templates.TemplateResponse(
        request,
        _interview_template_name(context),
        context,
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
