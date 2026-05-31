# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration form parsing and connection testing."""

from app.ai.llm_models import normalize_model_id
from app.platform.services.config import AppConfig, ConfigService
from app.platform.services.llm_catalog import LLMCatalogService
from app.question_voice.services.rules.voices import default_voice_for_locale
from app.shared.locales import normalize_locale
from app.speech.services.rules.speech_models import normalize_speech_model_size


class ConfigFormService:
    """Parse configuration form submissions and test provider connectivity."""

    @staticmethod
    async def parse_and_test(
        config_service: type[ConfigService],
        *,
        llm_preset_id: str,
        api_key: str,
        timeout: float,
        locale: str,
        speech_model_size: str,
        question_voice_enabled: bool,
    ) -> tuple[AppConfig, bool, str]:
        """Parse the config form, build ``AppConfig``, and test the connection.

        Args:
            config_service: Provider configuration service.
            llm_preset_id: Selected catalog model id from the form.
            api_key: API key field value (may be empty or masked).
            timeout: Request timeout in seconds.
            locale: Interview locale code.
            speech_model_size: Whisper model size slug.
            question_voice_enabled: Whether question voice is enabled.

        Returns:
            Tuple of configuration, connection success flag, and message.
        """
        existing = config_service.get_config()
        try:
            normalized_preset_id = normalize_model_id(
                llm_preset_id, LLMCatalogService.load_catalog()
            )
        except ValueError as exc:
            fallback = existing or AppConfig(
                provider_type="openai-compatible",
                base_url="",
                model="",
                locale=normalize_locale(locale),
                speech_model_size=normalize_speech_model_size(speech_model_size),
                question_voice_enabled=question_voice_enabled,
            )
            return fallback, False, str(exc)

        entry = LLMCatalogService.get_model(normalized_preset_id)
        if entry is None:
            return (
                existing
                or AppConfig(
                    provider_type="openai-compatible",
                    base_url="",
                    model="",
                ),
                False,
                "Interview model not found",
            )

        normalized_locale = normalize_locale(locale)
        keep_existing_voice = (
            existing is not None
            and normalize_locale(existing.locale) == normalized_locale
        )
        if keep_existing_voice and existing is not None:
            tts_voice_id = existing.tts_voice_id
        else:
            tts_voice_id = default_voice_for_locale(normalized_locale)

        config = AppConfig(
            provider_type=entry.provider_type,
            base_url=entry.base_url,
            model=entry.model,
            api_key=AppConfig.resolve_api_key_from_form(api_key, normalized_preset_id),
            timeout=timeout,
            locale=normalized_locale,
            speech_model_size=normalize_speech_model_size(speech_model_size),
            question_voice_enabled=question_voice_enabled,
            tts_voice_id=tts_voice_id,
            llm_preset_id=normalized_preset_id,
        )
        success, message = await config_service.test_interview_model(
            config,
            accepts_audio_input=entry.accepts_audio_input,
        )
        return config, success, message
