# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for question-voice API handlers."""

from typing import Annotated

from fastapi import Depends

from app.question_voice.services.piper_voice import PiperVoiceService


def get_piper_voice_service() -> type[PiperVoiceService]:
    """Return the Piper voice service class used by API handlers."""
    return PiperVoiceService


PiperVoiceServiceDep = Annotated[
    type[PiperVoiceService],
    Depends(get_piper_voice_service),
]
