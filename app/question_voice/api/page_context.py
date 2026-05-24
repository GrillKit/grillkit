# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Template context helpers for question-voice status on HTML pages."""

from typing import Any

from app.platform.services.config import ProviderConfig
from app.question_voice.services.piper_voice import PiperVoiceService, PiperVoiceStatus


def _show_voice_banner(status: PiperVoiceStatus) -> bool:
    """Return whether the interview page should show a question-voice banner."""
    if status.state in ("missing", "error", "downloading"):
        return True
    return status.state == "ready" and not status.loaded_in_memory


async def build_question_voice_page_context(
    config: ProviderConfig | None,
) -> dict[str, Any]:
    """Build Piper voice status keys for config and interview templates.

    Args:
        config: Saved provider configuration, or None when unset.

    Returns:
        Dict with ``tts_voice_status`` and ``tts_voice_banner``.
    """
    if config is None or not config.question_voice_enabled:
        return {
            "tts_voice_status": None,
            "tts_voice_banner": False,
        }

    status = PiperVoiceService.get_status(config.tts_voice_id, config.locale)
    return question_voice_context_from_status(status)


def question_voice_context_from_status(status: PiperVoiceStatus) -> dict[str, Any]:
    """Build template context from an existing Piper voice status snapshot.

    Args:
        status: Piper voice installation and load status.

    Returns:
        Dict with ``tts_voice_status`` and ``tts_voice_banner``.
    """
    return {
        "tts_voice_status": status,
        "tts_voice_banner": _show_voice_banner(status),
    }
