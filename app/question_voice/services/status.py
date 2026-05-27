# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Piper voice status resolution for API and templates."""

from app.platform.services.config import AppConfig
from app.question_voice.schemas import PiperVoiceStatusRead
from app.question_voice.services.piper_voice import PiperVoiceService
from app.question_voice.services.rules.voices import default_voice_for_locale
from app.shared.locales import SUPPORTED_LOCALES, normalize_locale


class QuestionVoiceStatusService:
    """Resolve Piper voice status from provider configuration."""

    @staticmethod
    def resolve_for_config(
        config: AppConfig | None,
    ) -> tuple[PiperVoiceStatusRead, bool]:
        """Build voice status and whether question voice is enabled.

        Args:
            config: Saved provider configuration, if any.

        Returns:
            Voice status read model and enabled flag for API consumers.
        """
        if config is None or not config.question_voice_enabled:
            voice_id = (
                config.tts_voice_id
                if config is not None
                else default_voice_for_locale("en")
            )
            locale = normalize_locale(config.locale if config is not None else "en")
            return (
                PiperVoiceStatusRead(
                    voice_id=voice_id,
                    locale=locale,
                    locale_label=SUPPORTED_LOCALES.get(locale, locale),
                    state="missing",
                    percent=0,
                    message="Question voice is disabled in configuration.",
                    voice_display_name=voice_id,
                ),
                False,
            )

        return (
            PiperVoiceService.get_status(config.tts_voice_id, config.locale),
            True,
        )

    @staticmethod
    def api_payload(
        status: PiperVoiceStatusRead,
        *,
        enabled: bool,
    ) -> dict[str, object]:
        """Serialize Piper voice status for JSON responses.

        Args:
            status: Piper voice status read model.
            enabled: Whether question voice is enabled in configuration.

        Returns:
            JSON-serializable status dictionary.
        """
        payload = status.model_dump()
        payload["state"] = status.state if enabled else "unavailable"
        payload["enabled"] = enabled
        return payload
