# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Resolve a loaded speech transcriber through the speech runtime coordinator."""

from app.ai.speech_transcriber import SpeechTranscriber
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator

_UNLOADED_MESSAGE = "Speech model is not loaded. Download it in Configuration."


async def resolve_speech_transcriber(
    coordinator: SpeechRuntimeCoordinator,
) -> SpeechTranscriber | None:
    """Return a loaded speech transcriber, attempting runtime load when needed.

    Args:
        coordinator: App-lifetime speech runtime coordinator.

    Returns:
        Loaded transcriber, or None when a model is unavailable.
    """
    transcriber = coordinator.get_transcriber()
    if transcriber is None:
        config = coordinator.config_service.get_config()
        if config is not None:
            await coordinator.sync_whisper(config)
            transcriber = coordinator.get_transcriber()
    return transcriber


def speech_transcriber_unavailable_message(
    coordinator: SpeechRuntimeCoordinator,
) -> str:
    """Build a user-facing message when no speech transcriber is loaded.

    Args:
        coordinator: App-lifetime speech runtime coordinator.

    Returns:
        Error text including optional model load error details.
    """
    load_error = coordinator.load_error()
    detail = f" Speech model load error: {load_error}" if load_error else ""
    return _UNLOADED_MESSAGE + detail
