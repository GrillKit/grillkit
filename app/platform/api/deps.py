# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for platform (config) API handlers."""

from typing import Annotated

from fastapi import Depends, Request

from app.platform.domain.config import ConfigService
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator


def get_config_service() -> type[ConfigService]:
    """Return the config service class used by API handlers."""
    return ConfigService


ConfigServiceDep = Annotated[type[ConfigService], Depends(get_config_service)]


def get_speech_runtime(request: Request) -> SpeechRuntimeCoordinator:
    """Return the app-lifetime speech runtime coordinator."""
    return request.app.state.speech_runtime


SpeechRuntimeDep = Annotated[
    SpeechRuntimeCoordinator,
    Depends(get_speech_runtime),
]
