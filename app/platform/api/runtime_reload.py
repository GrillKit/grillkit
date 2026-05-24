# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Reload speech and question-voice runtimes after configuration changes."""

from app.platform.services.config import ProviderConfig
from app.platform.services.speech_runtime import SpeechRuntimeCoordinator


async def reload_speech_runtimes_after_config_save(config: ProviderConfig) -> None:
    """Load or unload Whisper and Piper based on saved configuration.

    Args:
        config: Configuration that was just persisted.
    """
    await SpeechRuntimeCoordinator.reload_after_config_save(config)


def unload_speech_runtimes() -> None:
    """Unload in-process Whisper and Piper models."""
    SpeechRuntimeCoordinator.unload_all()
