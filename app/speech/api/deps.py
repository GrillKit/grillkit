# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for speech feature API handlers."""

from typing import Annotated

from fastapi import Depends

from app.speech.services.whisper_model import WhisperModelService


def get_whisper_model_service() -> type[WhisperModelService]:
    """Return the Whisper model service class used by API handlers."""
    return WhisperModelService


WhisperModelServiceDep = Annotated[
    type[WhisperModelService],
    Depends(get_whisper_model_service),
]
