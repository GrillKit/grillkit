# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Content negotiation helpers for status and download endpoints."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.templating import templates


def accepts_json(request: Request) -> bool:
    """Return whether the client prefers a JSON response."""
    return "application/json" in request.headers.get("accept", "")


def negotiated_response(
    request: Request,
    json_payload: dict[str, Any],
    template_name: str,
    template_context: dict[str, Any],
) -> Response:
    """Return JSON or an HTML partial depending on the Accept header.

    Args:
        request: FastAPI request object.
        json_payload: Body for ``application/json`` clients.
        template_name: Jinja2 template for HTML clients.
        template_context: Context passed to the template.

    Returns:
        JSON or template response.
    """
    if accepts_json(request):
        return JSONResponse(json_payload)
    return templates.TemplateResponse(
        request,
        template_name,
        template_context,
    )
