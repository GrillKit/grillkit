# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""API endpoint modules.

This package contains all API endpoint modules for the GrillKit application.
"""

from app.api.config import router as config_router
from app.api.dashboard import router as dashboard_router
from app.api.interview import router as interview_router
from app.api.setup import router as setup_router

__all__ = [
    "config_router",
    "dashboard_router",
    "interview_router",
    "setup_router",
]
