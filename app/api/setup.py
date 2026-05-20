# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup endpoint module.

This module provides the setup page for configuring interview parameters
and creating new interview sessions.
"""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.api.deps import ConfigServiceDep, InterviewCreationServiceDep
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
async def setup_page(request: Request, config_service: ConfigServiceDep) -> Response:
    """Setup page for interview configuration.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.

    Returns:
        HTML response with setup form, or redirect to config when unset.
    """
    if redirect := _redirect_if_no_config(config_service):
        return redirect
    return templates.TemplateResponse(
        request,
        "setup.html",
        setup_form_context(),
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
    language: str = Form(...),
    topic: str = Form(...),
    level: str = Form(...),
    locale: str = Form("en"),
    question_count: int = Form(5),
) -> Response:
    """Create interview session.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        interview_creation: Interview creation service.
        language: Programming language question bank slug.
        topic: Question category (YAML topic slug).
        level: Difficulty level (junior, middle, senior).
        locale: Language for AI feedback and follow-ups.
        question_count: Number of questions.

    Returns:
        Redirect to interview session page, config, or back to setup on error.
    """
    if redirect := _redirect_if_no_config(config_service):
        return redirect
    try:
        interview = interview_creation.create_interview(
            language=language,
            level=level,
            category=topic,
            locale=locale,
            question_count=question_count,
        )
        return RedirectResponse(
            url=f"/interview/{interview.id}",
            status_code=303,
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "setup.html",
            setup_form_context(language=language, level=level, error=str(e)),
        )
