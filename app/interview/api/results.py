# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Completed session results and section review pages."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.coding.services.review import CodingReviewService
from app.interview.services.results_page import SessionResultsPageService
from app.templating import templates
from app.theory.services.review import TheoryReviewService

router = APIRouter(prefix="/interview", tags=["interview-results"])


@router.get("/{interview_id}/results", response_class=HTMLResponse)
async def session_results_page(
    request: Request,
    interview_id: str,
) -> Response:
    """Render the completed session results hub.

    Args:
        request: FastAPI request object.
        interview_id: Session UUID.

    Returns:
        HTML response with session results, or redirect when unavailable.
    """
    page = SessionResultsPageService.prepare_page(interview_id)
    if page.redirect_url is not None:
        return RedirectResponse(url=page.redirect_url, status_code=303)
    return templates.TemplateResponse(
        request,
        "session_results.html",
        page.template_context or {},
    )


@router.get("/{interview_id}/theory", response_class=HTMLResponse)
async def theory_review_page(
    request: Request,
    interview_id: str,
) -> Response:
    """Render the completed theory section review with chat history.

    Args:
        request: FastAPI request object.
        interview_id: Session UUID.

    Returns:
        HTML response with theory review, or redirect when unavailable.
    """
    context = TheoryReviewService.build_context(interview_id)
    if context is None:
        return RedirectResponse(
            url=f"/interview/{interview_id}/results", status_code=303
        )
    return templates.TemplateResponse(
        request,
        "theory_review.html",
        context.model_dump(),
    )


@router.get("/{interview_id}/coding", response_class=HTMLResponse)
async def coding_review_page(
    request: Request,
    interview_id: str,
) -> Response:
    """Render the completed coding section review with per-task feedback.

    Args:
        request: FastAPI request object.
        interview_id: Session UUID.

    Returns:
        HTML response with coding review, or redirect when unavailable.
    """
    context = CodingReviewService.build_context(interview_id)
    if context is None:
        return RedirectResponse(
            url=f"/interview/{interview_id}/results", status_code=303
        )
    return templates.TemplateResponse(
        request,
        "coding_review.html",
        context.model_dump(),
    )
