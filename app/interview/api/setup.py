# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup endpoint module.

This module provides the setup page for configuring interview parameters
and creating new interview sessions.
"""

from dataclasses import replace

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.coding.services.availability import (
    is_coding_available_async,
)
from app.interview.api.deps import SessionCreationServiceDep
from app.interview.api.setup_form import setup_form_context
from app.interview.services.rules.selection import (
    parse_session_json,
    validate_session_selection,
)
from app.platform.api.deps import ConfigServiceDep
from app.shared import coding as coding_bank
from app.shared.questions import list_categories, list_levels, list_tracks
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.services.page import SpeechModelPageService
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
            **SpeechModelPageService.build_page_context(
                config,
                whisper_model_service=whisper_model_service,
            ).model_dump(),
        },
    )


@router.get("/options")
async def setup_options(
    track: str | None = None,
    level: str | None = None,
) -> JSONResponse:
    """Return cascaded setup options for dynamic form updates.

    Args:
        track: When set, returns levels for that question bank track.
        level: When set with track, returns categories for that pair.

    Returns:
        JSON with ``tracks``, ``levels``, or ``categories`` keys.
    """
    if track is None:
        return JSONResponse({"tracks": list_tracks()})

    tracks = list_tracks()
    if track not in tracks:
        raise HTTPException(status_code=404, detail=f"Unknown track: {track}")

    if level is None:
        return JSONResponse({"levels": list_levels(track)})

    levels = list_levels(track)
    if level not in levels:
        raise HTTPException(status_code=404, detail=f"Unknown level: {level}")

    return JSONResponse({"categories": sorted(list_categories(track, level))})


@router.get("/coding-options")
async def setup_coding_options(
    track: str | None = None,
    level: str | None = None,
) -> JSONResponse:
    """Return cascaded setup options for the coding task bank.

    Args:
        track: When set, returns levels for that coding track.
        level: When set with track, returns categories for that pair.

    Returns:
        JSON with ``tracks``, ``levels``, or ``categories`` keys.
    """
    if track is None:
        return JSONResponse({"tracks": coding_bank.list_tracks()})

    tracks = coding_bank.list_tracks()
    if track not in tracks:
        raise HTTPException(status_code=404, detail=f"Unknown coding track: {track}")

    if level is None:
        return JSONResponse({"levels": coding_bank.list_levels(track)})

    levels = coding_bank.list_levels(track)
    if level not in levels:
        raise HTTPException(status_code=404, detail=f"Unknown coding level: {level}")

    return JSONResponse(
        {"categories": sorted(coding_bank.list_categories(track, level))}
    )


@router.get("/coding-available")
async def setup_coding_available() -> JSONResponse:
    """Return whether coding sessions can be started from setup.

    Returns:
        JSON with ``available`` boolean.
    """
    return JSONResponse({"available": await is_coding_available_async()})


@router.post("", response_class=HTMLResponse)
async def create_interview(
    request: Request,
    config_service: ConfigServiceDep,
    session_creation: SessionCreationServiceDep,
    whisper_model_service: WhisperModelServiceDep,
    selection_json: str = Form(...),
    question_count: int = Form(5),
    coding_question_count: int = Form(2),
    enable_question_timer: str | None = Form(None),
    question_time_minutes: int = Form(3),
    enable_coding_timer: str | None = Form(None),
    coding_time_minutes: int = Form(10),
) -> Response:
    """Create interview session from multi-track setup selection.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        session_creation: Session creation service.
        whisper_model_service: Whisper model download service.
        selection_json: JSON payload built by the setup form script.
        question_count: Number of theory questions.
        coding_question_count: Number of coding tasks.
        enable_question_timer: Present when the theory timer checkbox is checked.
        question_time_minutes: Per-round theory limit in minutes when enabled.
        enable_coding_timer: Present when the coding timer checkbox is checked.
        coding_time_minutes: Per-task coding limit in minutes when enabled.

    Returns:
        Redirect to interview session page, config, or back to setup on error.
    """
    if redirect := _redirect_if_no_config(config_service):
        return redirect
    config = config_service.get_config()
    if config is None:
        return _CONFIG_REDIRECT

    theory_timer_seconds: int | None = None
    if enable_question_timer:
        minutes = max(1, question_time_minutes)
        theory_timer_seconds = minutes * 60

    coding_timer_seconds: int | None = None
    if enable_coding_timer:
        minutes = max(1, coding_time_minutes)
        coding_timer_seconds = minutes * 60

    clamped_theory_count = _clamp_question_count(question_count)
    clamped_coding_count = _clamp_question_count(coding_question_count)

    try:
        session = parse_session_json(selection_json)
        session = replace(
            session,
            theory=replace(
                session.theory,
                question_count=clamped_theory_count,
                task_time_limit_seconds=theory_timer_seconds,
            ),
            coding=replace(
                session.coding,
                question_count=clamped_coding_count,
                task_time_limit_seconds=coding_timer_seconds,
            ),
        )
        validate_session_selection(session)
        interview = session_creation.create_session(
            session,
            locale=config.locale,
        )
        return RedirectResponse(
            url=f"/interview/{interview.id}",
            status_code=303,
        )
    except ValueError as e:
        min_theory = _MIN_QUESTIONS
        min_coding = _MIN_QUESTIONS
        try:
            parsed = parse_session_json(selection_json)
            if parsed.theory.enabled:
                min_theory = max(_MIN_QUESTIONS, parsed.theory_selection.topic_count)
            if parsed.coding.enabled:
                min_coding = max(_MIN_QUESTIONS, parsed.coding_selection.topic_count)
        except ValueError:
            pass
        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                **setup_form_context(
                    locale=config.locale,
                    error=str(e),
                    min_question_count=min_theory,
                    min_coding_task_count=min_coding,
                    initial_wizard_step="review",
                ),
                **SpeechModelPageService.build_page_context(
                    config,
                    whisper_model_service=whisper_model_service,
                ).model_dump(),
            },
        )
