# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Template context helpers for speech model status on HTML pages."""

from typing import Any

from app.services.config import ProviderConfig
from app.services.whisper_model import WhisperModelService, WhisperModelStatus


def build_speech_model_page_context(
    config: ProviderConfig | None,
    whisper_model_service: type[WhisperModelService],
) -> dict[str, Any]:
    """Build speech model keys shared by config, setup, and interview templates.

    Args:
        config: Saved provider configuration, or None when unset.
        whisper_model_service: Whisper model service class from FastAPI deps.

    Returns:
        Dict with ``speech_model_status``, ``speech_model_banner``, and ``status``
        (alias for ``speech_model_status.html``).
    """
    if config is None:
        return {
            "speech_model_status": None,
            "speech_model_banner": False,
            "status": None,
        }

    status = whisper_model_service.get_status(
        config.speech_model_size,
        config.locale,
    )
    return speech_model_context_from_status(status)


def speech_model_context_from_status(
    status: WhisperModelStatus,
) -> dict[str, Any]:
    """Build template context from an existing status snapshot.

    Args:
        status: Whisper install/load status for one size and locale.

    Returns:
        Dict with ``speech_model_status``, ``speech_model_banner``, and ``status``.
    """
    return {
        "speech_model_status": status,
        "speech_model_banner": status.state == "missing",
        "status": status,
    }
