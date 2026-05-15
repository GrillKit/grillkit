# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session endpoints.

This module provides HTTP endpoints for viewing and interacting
with interview sessions. All business logic is delegated to the
service layer.
"""

import json
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..services.interview_session import InterviewSessionService

router = APIRouter(prefix="/interview", tags=["interview"])
templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)


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

    # Find the first unanswered question
    current_question = None
    for answer in session.answers:
        if answer.answer_text is None:
            current_question = answer
            break

    # Parse overall_feedback JSON for the template
    overall_feedback_data = None
    if session.overall_feedback:
        try:
            overall_feedback_data = json.loads(session.overall_feedback)
        except json.JSONDecodeError:
            overall_feedback_data = {"overall_feedback": session.overall_feedback}

    # Calculate max possible score (5 per answered round, including follow-ups)
    answered_answers = [a for a in session.answers if a.answer_text is not None]
    max_score = len(answered_answers) * 5

    return templates.TemplateResponse(
        request,
        "interview.html",
        {
            "session": session,
            "answers": session.answers,
            "current_question": current_question,
            "overall_feedback": overall_feedback_data,
            "max_score": max_score,
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

    Delegates to InterviewSessionService which handles saving,
    AI evaluation, and follow-up generation.

    Args:
        request: FastAPI request object.
        session_id: The session UUID.
        question_id: The question ID being answered.
        answer_text: The user's answer text.

    Returns:
        Redirect to the interview page.
    """
    # Validate session exists and is still active
    session = InterviewSessionService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Cannot submit answer to a completed session",
        )

    try:
        await InterviewSessionService.process_answer_submission(
            session_id=session_id,
            question_id=question_id,
            answer_text=answer_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to process answer for session %s", session_id)
        raise HTTPException(status_code=502, detail=f"AI evaluation failed: {e}") from e

    return RedirectResponse(
        url=f"/interview/{session_id}",
        status_code=303,
    )


@router.post("/{session_id}/complete", response_class=HTMLResponse)
async def complete_interview(request: Request, session_id: str):
    """Mark an interview session as completed.

    Delegates to InterviewSessionService which handles AI evaluation
    of the entire session and saves overall feedback.

    Args:
        request: FastAPI request object.
        session_id: The session UUID.

    Returns:
        Redirect to the interview page.
    """
    try:
        await InterviewSessionService.process_session_completion(session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to complete session %s", session_id)
        raise HTTPException(
            status_code=502, detail=f"Session evaluation failed: {e}"
        ) from e

    return RedirectResponse(
        url=f"/interview/{session_id}",
        status_code=303,
    )
