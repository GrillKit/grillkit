# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding API transport layer.

This package aggregates all coding sub-routers into a single ``router``
that the application factory mounts via :func:`app.include_router`.
"""

from fastapi import APIRouter

from app.coding.api import routes

router = APIRouter()
router.include_router(routes.router)

__all__ = ["router"]
