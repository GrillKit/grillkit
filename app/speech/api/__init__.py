# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech feature HTTP and WebSocket endpoints.

This package aggregates all speech sub-routers into a single ``router``
that the application factory mounts via :func:`app.include_router`.
"""

from fastapi import APIRouter

from app.speech.api import dictation, routes

router = APIRouter()
router.include_router(routes.router)
router.include_router(dictation.router)

__all__ = ["router"]
