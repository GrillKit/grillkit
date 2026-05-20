# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Dashboard endpoint module.

This module provides the home page with interview history.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.deps import InterviewQueryDep
from app.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    interview_query: InterviewQueryDep,
) -> HTMLResponse:
    """Render the dashboard with recent interview history.

    Args:
        request: FastAPI request object.
        interview_query: Interview read service.

    Returns:
        HTML response with the dashboard template.
    """
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "interview_history": interview_query.list_dashboard_rows(limit=20),
        },
    )
