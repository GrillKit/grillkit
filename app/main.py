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

from app import __version__
from app.coding.api import router as coding_router
from app.interview.api import router as interview_router
from app.platform.api import router as platform_router
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator
from app.question_voice.api import router as question_voice_router
from app.shared.infrastructure.gateways.piper import PiperRuntime
from app.shared.infrastructure.gateways.whisper import WhisperRuntime
from app.shared.paths import STATIC_DIR
from app.speech.api import router as speech_router
from app.theory.api import router as theory_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Creates the speech runtime coordinator, loads the Whisper model (and Piper
    when configured) on startup, and unloads them on shutdown.
    """
    coordinator = SpeechRuntimeCoordinator(WhisperRuntime, PiperRuntime)
    app.state.speech_runtime = coordinator
    await coordinator.startup()
    yield
    await coordinator.shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="GrillKit",
        description="AI Interview Trainer",
        version=__version__,
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(interview_router)
    app.include_router(platform_router)
    app.include_router(theory_router)
    app.include_router(coding_router)
    app.include_router(speech_router)
    app.include_router(question_voice_router)

    return app


app = create_app()
