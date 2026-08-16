# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory HTTP and WebSocket transport (scaffold for Phase 4+).

This package aggregates all theory sub-routers into a single ``router``
that the application factory mounts via :func:`app.include_router`.
"""

from fastapi import APIRouter

from app.theory.api import routes

router = APIRouter()
router.include_router(routes.router)

__all__ = ["router"]
