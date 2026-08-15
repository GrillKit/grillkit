# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Platform HTTP endpoints.

This package aggregates all platform sub-routers into a single ``router``
that the application factory mounts via :func:`app.include_router`.
"""

from fastapi import APIRouter

from app.platform.api import config

router = APIRouter()
router.include_router(config.router)

__all__ = ["router"]
