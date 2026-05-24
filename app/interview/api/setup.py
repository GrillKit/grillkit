# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup endpoint module.

This module provides the setup page for configuring interview parameters
and creating new interview sessions.
"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.interview.api.deps import InterviewCreationServiceDep
from app.interview.api.setup_form import setup_form_context
from app.interview.domain.selection import parse_selection_json, validate_question_count
from app.platform.api.deps import ConfigServiceDep
from app.questions import list_categories, list_languages, list_levels
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.api.page_context import build_speech_model_page_context
from app.templating import templates

router = APIRouter(prefix="/setup", tags=["setup"])

_CONFIG_REDIRECT = RedirectResponse(url="/config", status_code=303)
_MIN_QUESTIONS = 1
_MAX_QUESTIONS = 20


def _redirect_if_no_config(config_service: ConfigServiceDep) -> RedirectResponse | None:
    """Return a redirect to the config page when AI provider is not configured."""
    if config_service.get_config() is None:
        return _CONFIG_REDIRECT
    return None


def _clamp_question_count(value: int) -> int:
    """Clamp question count to the allowed setup range.

    Args:
        value: Raw question count from the form.

    Returns:
        Value between ``_MIN_QUESTIONS`` and ``_MAX_QUESTIONS``.
    """
    return max(_MIN_QUESTIONS, min(_MAX_QUESTIONS, value))


@router.get("", response_class=HTMLResponse)
async def setup_page(
    request: Request,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> Response:
    """Setup page for interview configuration.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML response with setup form, or redirect to config when unset.
    """
    if redirect := _redirect_if_no_config(config_service):
        return redirect
    config = config_service.get_config()
    if config is None:
        return _CONFIG_REDIRECT
    return templates.TemplateResponse(
        request,
        "setup.html",
        {
            **setup_form_context(locale=config.locale),
            **build_speech_model_page_context(config, whisper_model_service),
        },
    )


@router.get("/options")
async def setup_options(
    language: str | None = None,
    level: str | None = None,
) -> JSONResponse:
    """Return cascaded setup options for dynamic form updates.

    Args:
        language: When set, returns levels for that language.
        level: When set with language, returns categories for that pair.

    Returns:
        JSON with ``languages``, ``levels``, or ``categories`` keys.
    """
    if language is None:
        return JSONResponse({"languages": list_languages()})

    languages = list_languages()
    if language not in languages:
        raise HTTPException(status_code=404, detail=f"Unknown language: {language}")

    if level is None:
        return JSONResponse({"levels": list_levels(language)})

    levels = list_levels(language)
    if level not in levels:
        raise HTTPException(status_code=404, detail=f"Unknown level: {level}")

    return JSONResponse({"categories": sorted(list_categories(language, level))})


@router.post("", response_class=HTMLResponse)
async def create_interview(
    request: Request,
    config_service: ConfigServiceDep,
    interview_creation: InterviewCreationServiceDep,
    whisper_model_service: WhisperModelServiceDep,
    selection_json: str = Form(...),
    question_count: int = Form(5),
    enable_question_timer: str | None = Form(None),
    question_time_minutes: int = Form(3),
) -> Response:
    """Create interview session from multi-language setup selection.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        interview_creation: Interview creation service.
        whisper_model_service: Whisper model download service.
        selection_json: JSON payload built by the setup form script.
        question_count: Number of questions.
        enable_question_timer: Present when the timer checkbox is checked.
        question_time_minutes: Per-round limit in minutes when the timer is enabled.

    Returns:
        Redirect to interview session page, config, or back to setup on error.
    """
    if redirect := _redirect_if_no_config(config_service):
        return redirect
    config = config_service.get_config()
    if config is None:
        return _CONFIG_REDIRECT

    timer_seconds: int | None = None
    if enable_question_timer:
        minutes = max(1, question_time_minutes)
        timer_seconds = minutes * 60

    clamped_count = _clamp_question_count(question_count)

    try:
        selection = parse_selection_json(selection_json)
        validate_question_count(selection, clamped_count)
        interview = interview_creation.create_interview(
            selection=selection,
            locale=config.locale,
            question_count=clamped_count,
            question_time_limit_seconds=timer_seconds,
        )
        return RedirectResponse(
            url=f"/interview/{interview.id}",
            status_code=303,
        )
    except ValueError as e:
        min_count = _MIN_QUESTIONS
        try:
            selection = parse_selection_json(selection_json)
            min_count = max(_MIN_QUESTIONS, selection.topic_count)
        except ValueError:
            pass
        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                **setup_form_context(
                    locale=config.locale,
                    error=str(e),
                    min_question_count=min_count,
                ),
                **build_speech_model_page_context(config, whisper_model_service),
            },
        )
