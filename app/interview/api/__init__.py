# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview feature HTTP and WebSocket endpoints.

This package aggregates all interview sub-routers into a single ``router``
that the application factory mounts via :func:`app.include_router`.
"""

from fastapi import APIRouter

from app.interview.api import dashboard, known_questions, results, routes, setup

router = APIRouter()
router.include_router(dashboard.router)
router.include_router(setup.router)
router.include_router(known_questions.router)
router.include_router(routes.router)
router.include_router(results.router)

__all__ = ["router"]
