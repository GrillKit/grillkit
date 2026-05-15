# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides HTTP endpoints for viewing and interacting
with interview sessions (WebSocket will be added later).
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..services.interview_session import InterviewSessionService

router = APIRouter(prefix="/interview", tags=["interview"])
templates = Jinja2Templates(directory="templates")


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

    # Find the first unanswered question (round=0, answer_text is None)
    current_question = None
    for answer in session.answers:
        if answer.round == 0 and answer.answer_text is None:
            current_question = answer
            break

    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "session": session,
            "answers": session.answers,
            "current_question": current_question,
        },
    )


@router.post("/{session_id}/answer", response_class=HTMLResponse)
async def submit_answer(
    request: Request,
    session_id: str,
    question_id: str = Form(...),
    answer_text: str = Form(...),
):
    """Submit an answer for the current question.

    Saves the answer and redirects back to the interview page.

    Args:
        request: FastAPI request object.
        session_id: The session UUID.
        question_id: The question ID being answered.
        answer_text: The user's answer text.

    Returns:
        Redirect to the interview page.
    """
    InterviewSessionService.submit_answer(
        session_id=session_id,
        question_id=question_id,
        answer_text=answer_text,
    )
    return RedirectResponse(
        url=f"/interview/{session_id}",
        status_code=303,
    )
