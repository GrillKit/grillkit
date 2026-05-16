# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Root endpoint module.

This module provides the root endpoint for redirecting users to
dashboard (if configured) or setup page (if not configured).
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.config import ConfigService

router = APIRouter(tags=["root"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Root endpoint redirects to dashboard or setup based on configuration.

    Args:
        request: FastAPI request object.

    Returns:
        HTML response with dashboard (if configured) or setup page.
    """
    config = ConfigService.get_config()
    if config:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {},
        )
    return templates.TemplateResponse(
        request,
        "setup.html",
        {},
    )
