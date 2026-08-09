# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""HTTP API for known bank-item exclusions."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app.interview.schemas.known_questions import KnownItemMutation, KnownItemsResponse
from app.interview.support.bank_text import resolve_known_views
from app.shared.application.uow_deps import UoWAutoCommitDep
from app.templating import templates

router = APIRouter(prefix="/known-questions", tags=["known-questions"])


@router.get("")
def list_known_questions(
    uow: UoWAutoCommitDep,
) -> KnownItemsResponse:
    """Return all known bank item IDs grouped by branch."""
    grouped = uow.known_questions.list_all_grouped()
    return KnownItemsResponse(
        theory=grouped.get("theory", []),
        coding=grouped.get("coding", []),
    )


@router.post("")
def mark_known_item(
    body: KnownItemMutation,
    uow: UoWAutoCommitDep,
) -> KnownItemsResponse:
    """Mark a bank item as known for future session exclusion."""
    uow.known_questions.mark(body.branch, body.item_id)
    grouped = uow.known_questions.list_all_grouped()
    return KnownItemsResponse(
        theory=grouped.get("theory", []),
        coding=grouped.get("coding", []),
    )


@router.delete("")
def unmark_known_item(
    body: KnownItemMutation,
    uow: UoWAutoCommitDep,
) -> KnownItemsResponse:
    """Remove a bank item from the known list."""
    uow.known_questions.unmark(body.branch, body.item_id)
    grouped = uow.known_questions.list_all_grouped()
    return KnownItemsResponse(
        theory=grouped.get("theory", []),
        coding=grouped.get("coding", []),
    )


@router.get("/manage", response_class=HTMLResponse)
async def manage_known_questions_page(
    request: Request,
    uow: UoWAutoCommitDep,
) -> Response:
    """Render the known bank items management page."""
    known = resolve_known_views(uow.known_questions.list_all_grouped())
    return templates.TemplateResponse(
        request,
        "known_questions.html",
        {
            "theory_items": known.get("theory", []),
            "coding_items": known.get("coding", []),
            "total_count": uow.known_questions.count(),
        },
    )
