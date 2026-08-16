# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""HTTP routes for question-voice (TTS status).

This package aggregates all question-voice sub-routers into a single
``router`` that the application factory mounts via :func:`app.include_router`.
"""

from fastapi import APIRouter

from app.question_voice.api import routes

router = APIRouter()
router.include_router(routes.router)

__all__ = ["router"]
