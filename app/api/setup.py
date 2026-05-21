# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup endpoint module.

This module provides the setup page for configuring interview parameters
and creating new interview sessions.
"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.api.deps import (
    ConfigServiceDep,
    InterviewCreationServiceDep,
    WhisperModelServiceDep,
)
from app.api.setup_form import setup_form_context
from app.questions import list_categories, list_languages, list_levels
from app.templating import templates

router = APIRouter(prefix="/setup", tags=["setup"])

_CONFIG_REDIRECT = RedirectResponse(url="/config", status_code=303)


def _redirect_if_no_config(config_service: ConfigServiceDep) -> RedirectResponse | None:
    """Return a redirect to the config page when AI provider is not configured."""
    if config_service.get_config() is None:
        return _CONFIG_REDIRECT
    return None


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
    speech_status = whisper_model_service.get_status(
        config.speech_model_size,
        config.locale,
    )
    return templates.TemplateResponse(
        request,
        "setup.html",
        {
            **setup_form_context(locale=config.locale),
            "speech_model_banner": speech_status.state == "missing",
            "speech_model_status": speech_status,
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
    language: str = Form(...),
    topic: str = Form(...),
    level: str = Form(...),
    question_count: int = Form(5),
) -> Response:
    """Create interview session.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        interview_creation: Interview creation service.
        whisper_model_service: Whisper model download service.
        language: Programming language question bank slug.
        topic: Question category (YAML topic slug).
        level: Difficulty level (junior, middle, senior).
        question_count: Number of questions.

    Returns:
        Redirect to interview session page, config, or back to setup on error.
    """
    if redirect := _redirect_if_no_config(config_service):
        return redirect
    config = config_service.get_config()
    if config is None:
        return _CONFIG_REDIRECT
    try:
        interview = interview_creation.create_interview(
            language=language,
            level=level,
            category=topic,
            locale=config.locale,
            question_count=question_count,
        )
        return RedirectResponse(
            url=f"/interview/{interview.id}",
            status_code=303,
        )
    except ValueError as e:
        speech_status = whisper_model_service.get_status(
            config.speech_model_size,
            config.locale,
        )
        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                **setup_form_context(
                    locale=config.locale,
                    language=language,
                    level=level,
                    error=str(e),
                ),
                "speech_model_banner": speech_status.state == "missing",
                "speech_model_status": speech_status,
            },
        )
