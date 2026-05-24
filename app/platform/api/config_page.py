# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Template context helpers for the configuration page."""

from typing import Any

from app.platform.api.llm_page_context import build_llm_page_context
from app.platform.services.config import ProviderConfig
from app.question_voice.api.page_context import build_question_voice_page_context
from app.shared.domain.locales import SUPPORTED_LOCALES
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.api.page_context import build_speech_model_page_context
from app.speech.domain.models import SPEECH_MODEL_BY_SIZE


async def build_config_page_context(
    *,
    config: ProviderConfig | None,
    whisper_model_service: WhisperModelServiceDep,
    error: str | None = None,
    message: str | None = None,
    mask_secret: bool = True,
) -> dict[str, Any]:
    """Build the full Jinja context for ``config.html``.

    Args:
        config: Saved provider configuration, if any.
        whisper_model_service: Whisper model download service class.
        error: Optional form validation or connection error message.
        message: Optional success or informational message.
        mask_secret: Whether to mask the API key in the config dict.

    Returns:
        Context dict for ``config.html``.
    """
    voice_ctx = await build_question_voice_page_context(config)
    llm_ctx = await build_llm_page_context(config)
    context: dict[str, Any] = {
        "config": config.to_dict(mask_secret=mask_secret) if config else None,
        "locales": SUPPORTED_LOCALES,
        "speech_model_specs": SPEECH_MODEL_BY_SIZE,
        **build_speech_model_page_context(config, whisper_model_service),
        **voice_ctx,
        **llm_ctx,
    }
    if error is not None:
        context["error"] = error
    if message is not None:
        context["message"] = message
    return context
