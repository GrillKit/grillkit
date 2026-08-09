# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI app factory.

This module provides the FastAPI application factory function
for creating the GrillKit application instance with all routes,
templates, and middleware configured.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.coding.api import routes as coding_router
from app.interview.api import dashboard as dashboard_router
from app.interview.api import known_questions as known_questions_router
from app.interview.api import results as results_router
from app.interview.api import routes as interview_router
from app.interview.api import setup as setup_router
from app.platform.api import config as config_router
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator
from app.question_voice.api import routes as question_voice_router
from app.shared.infrastructure.database import run_migrations
from app.shared.paths import STATIC_DIR
from app.speech.api import dictation as dictation_router
from app.speech.api import routes as speech_router
from app.theory.api import routes as theory_router


def _get_app_version() -> str:
    """Return the application version from package metadata.

    Falls back to a hardcoded value when the package is not installed
    (e.g., during development).

    Returns:
        Semantic version string.
    """
    try:
        from importlib.metadata import version

        return version("grillkit")
    except Exception:
        return "2026.6.12"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Initializes database and loads the Whisper model when installed.
    """
    run_migrations()
    await SpeechRuntimeCoordinator.startup(app)
    yield
    SpeechRuntimeCoordinator.unload_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="GrillKit",
        description="AI Interview Trainer",
        version=_get_app_version(),
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(dashboard_router.router)
    app.include_router(setup_router.router)
    app.include_router(known_questions_router.router)
    app.include_router(config_router.router)
    app.include_router(interview_router.router)
    app.include_router(results_router.router)
    app.include_router(theory_router.router)
    app.include_router(coding_router.router)
    app.include_router(dictation_router.router)
    app.include_router(speech_router.router)
    app.include_router(question_voice_router.router)

    return app


app = create_app()
