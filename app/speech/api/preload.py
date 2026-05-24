# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech runtime helpers for interview API handlers."""

from fastapi import FastAPI

from app.platform.services.config import ProviderConfig
from app.platform.services.speech_runtime import SpeechRuntimeCoordinator


async def preload_whisper_for_active_interview(
    app: FastAPI,
    config: ProviderConfig | None,
    *,
    interview_active: bool,
) -> None:
    """Bind Whisper to the app and load the configured model when needed.

    Args:
        app: FastAPI application instance.
        config: Saved provider configuration.
        interview_active: Whether the interview session is still active.
    """
    await SpeechRuntimeCoordinator.preload_whisper_for_active_interview(
        app,
        config,
        interview_active=interview_active,
    )
