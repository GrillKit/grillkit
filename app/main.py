# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI app factory.

This module provides the FastAPI application factory function
for creating the GrillKit application instance with all routes,
templates, and middleware configured.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import config as config_router
from app.api import dashboard as dashboard_router
from app.api import interview as interview_router
from app.api import setup as setup_router
from app.database import init_db

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Initializes database on startup.
    """
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="GrillKit",
        description="AI Interview Trainer",
        version="2026.5.20",
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(dashboard_router.router)
    app.include_router(setup_router.router)
    app.include_router(config_router.router)
    app.include_router(interview_router.router)

    return app


app = create_app()
