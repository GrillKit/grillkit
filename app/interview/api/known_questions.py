# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""HTTP API for known bank-item exclusions."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.interview.api.deps import KnownQuestionsServiceDep
from app.interview.schemas.known_questions import KnownItemMutation, KnownItemsResponse
from app.templating import templates

router = APIRouter(prefix="/known-questions", tags=["known-questions"])


@router.get("")
def list_known_questions(
    service: KnownQuestionsServiceDep,
) -> KnownItemsResponse:
    """Return all known bank item IDs grouped by branch.

    Args:
        service: Known questions service for the request scope.

    Returns:
        Theory and coding ID lists.
    """
    grouped = service.list_all()
    return KnownItemsResponse(
        theory=grouped.get("theory", []),
        coding=grouped.get("coding", []),
    )


@router.post("")
def mark_known_item(
    body: KnownItemMutation,
    service: KnownQuestionsServiceDep,
) -> KnownItemsResponse:
    """Mark a bank item as known for future session exclusion.

    Args:
        body: Branch and bank item ID to mark.
        service: Known questions service for the request scope.

    Returns:
        Updated known item lists.
    """
    service.mark_known(body.branch, body.item_id)
    grouped = service.list_all()
    return KnownItemsResponse(
        theory=grouped.get("theory", []),
        coding=grouped.get("coding", []),
    )


@router.delete("")
def unmark_known_item(
    body: KnownItemMutation,
    service: KnownQuestionsServiceDep,
) -> KnownItemsResponse:
    """Remove a bank item from the known list.

    Args:
        body: Branch and bank item ID to unmark.
        service: Known questions service for the request scope.

    Returns:
        Updated known item lists.
    """
    service.unmark(body.branch, body.item_id)
    grouped = service.list_all()
    return KnownItemsResponse(
        theory=grouped.get("theory", []),
        coding=grouped.get("coding", []),
    )


@router.get("/manage", response_class=HTMLResponse)
async def manage_known_questions_page(
    request: Request,
    service: KnownQuestionsServiceDep,
) -> Response:
    """Render the known bank items management page.

    Args:
        request: FastAPI request object.
        service: Known questions service for the request scope.

    Returns:
        HTML page listing known items with unmark actions.
    """
    known = service.list_all_with_text()
    return templates.TemplateResponse(
        request,
        "known_questions.html",
        {
            "theory_items": known.get("theory", []),
            "coding_items": known.get("coding", []),
            "total_count": service.count(),
        },
    )
