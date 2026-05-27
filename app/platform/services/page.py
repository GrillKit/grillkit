# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration page context builder."""

from app.platform.schemas import (
    ConfigPageContext,
    app_config_read_from,
    speech_model_specs_for_config,
)
from app.platform.services.config import AppConfig
from app.platform.services.llm_page import LLMPageService
from app.question_voice.services.page import QuestionVoicePageService
from app.shared.locales import SUPPORTED_LOCALES
from app.speech.services.page import SpeechModelPageService
from app.speech.services.whisper_model import WhisperModelService


class ConfigPageService:
    """Build template context for the provider configuration page."""

    @staticmethod
    async def build_page_context(
        *,
        config: AppConfig | None,
        whisper_model_service: type[WhisperModelService] = WhisperModelService,
        error: str | None = None,
        message: str | None = None,
        mask_secret: bool = True,
        selected_llm_preset_id: str | None = None,
    ) -> ConfigPageContext:
        """Assemble the full context for ``config.html``.

        Args:
            config: Saved provider configuration, if any.
            whisper_model_service: Whisper model service class (injectable in tests).
            error: Optional form validation or connection error message.
            message: Optional success or informational message.
            mask_secret: Whether to mask the API key in the config dict.
            selected_llm_preset_id: Override selected preset after catalog edits.

        Returns:
            Frozen page context for the configuration template.
        """
        speech_ctx = SpeechModelPageService.build_page_context(
            config,
            whisper_model_service=whisper_model_service,
        )
        voice_ctx = await QuestionVoicePageService.build_page_context(config)
        preset_id = (
            selected_llm_preset_id
            if selected_llm_preset_id is not None
            else LLMPageService.resolve_selected_preset_id(config)
        )

        return ConfigPageContext(
            config=(
                app_config_read_from(config, mask_secret=mask_secret)
                if config
                else None
            ),
            locales=dict(SUPPORTED_LOCALES),
            speech_model_specs=speech_model_specs_for_config(),
            speech_model_status=speech_ctx.speech_model_status,
            speech_model_banner=speech_ctx.speech_model_banner,
            status=speech_ctx.status,
            tts_voice_status=voice_ctx.tts_voice_status,
            tts_voice_banner=voice_ctx.tts_voice_banner,
            llm_presets=LLMPageService.list_preset_options(),
            selected_llm_preset_id=preset_id,
            error=error,
            message=message,
        )
