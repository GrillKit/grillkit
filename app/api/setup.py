# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Setup endpoint module.

This module provides the setup page for configuring interview parameters
and creating new interview sessions.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..services.interview_session import InterviewSessionService

router = APIRouter(prefix="/setup", tags=["setup"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Setup page for interview configuration.

    Loads available question categories from the YAML bank
    and passes them to the template for the dropdown.

    Args:
        request: FastAPI request object.

    Returns:
        HTML response with setup form.
    """
    categories = InterviewSessionService.get_available_categories("python")
    return templates.TemplateResponse(
        request,
        "setup.html",
        {"categories": categories},
    )


@router.post("", response_class=HTMLResponse)
async def create_session(
    request: Request,
    topic: str = Form(...),
    level: str = Form(...),
    question_count: int = Form(5),
):
    """Create interview session.

    Loads questions from YAML bank for the selected topic and level,
    creates an InterviewSession with Answer records in the database,
    and redirects to the interview page.

    Args:
        request: FastAPI request object.
        topic: Interview topic (e.g., "python", "algorithms").
        level: Difficulty level ("junior", "middle", "senior").
        question_count: Number of questions.

    Returns:
        Redirect to interview session page or back to setup on error.
    """
    try:
        session = InterviewSessionService.create_session(
            language="python",
            level=level,
            category=topic,
            question_count=question_count,
        )
        return RedirectResponse(
            url=f"/interview/{session.id}",
            status_code=303,
        )
    except ValueError as e:
        categories = InterviewSessionService.get_available_categories("python")
        return templates.TemplateResponse(
            request,
            "setup.html",
            {
                "categories": categories,
                "error": str(e),
            },
        )
