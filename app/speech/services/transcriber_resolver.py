# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Resolve a loaded Whisper speech transcriber from application state."""

from typing import cast

from starlette.applications import Starlette

from app.ai.speech_transcriber import SpeechTranscriber
from app.platform.services.config import ConfigService
from app.speech.services.whisper_runtime import WhisperRuntime
from app.speech.services.whisper_storage import is_installed

_UNLOADED_MESSAGE = "Speech model is not loaded. Download it in Configuration."


async def resolve_speech_transcriber(
    app: Starlette,
    config_service: type[ConfigService],
) -> SpeechTranscriber | None:
    """Return a loaded speech transcriber, attempting runtime load when needed.

    Args:
        app: ASGI application with optional ``speech_transcriber`` on state.
        config_service: Provider configuration service class.

    Returns:
        Loaded transcriber, or None when Whisper is unavailable.
    """
    transcriber = getattr(app.state, "speech_transcriber", None)
    if transcriber is None:
        config = config_service.get_config()
        if config is not None and is_installed(config.speech_model_size):
            await WhisperRuntime.load_size(config.speech_model_size)
            transcriber = getattr(app.state, "speech_transcriber", None)
    if transcriber is None:
        return None
    return cast(SpeechTranscriber, transcriber)


def speech_transcriber_unavailable_message() -> str:
    """Build a user-facing message when no speech transcriber is loaded.

    Returns:
        Error text including optional Whisper load error details.
    """
    load_error = WhisperRuntime.load_error()
    detail = f" Speech model load error: {load_error}" if load_error else ""
    return _UNLOADED_MESSAGE + detail
