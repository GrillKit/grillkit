# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Piper voice status resolution for API and templates."""

from app.platform.services.config import AppConfig
from app.question_voice.schemas import PiperVoiceStatusRead
from app.question_voice.services.piper_voice import PiperVoiceService
from app.shared.locales import DEFAULT_LOCALE, normalize_locale
from app.shared.tts_voices import (
    default_voice_for_locale,
    normalize_tts_voice_id,
)


class QuestionVoiceStatusService:
    """Resolve Piper voice status from provider configuration."""

    @staticmethod
    def resolve_tts_target(
        config: AppConfig | None,
        *,
        locale: str | None = None,
        voice_id: str | None = None,
    ) -> tuple[str, str]:
        """Resolve Piper voice id and locale from saved config or query defaults.

        Args:
            config: Saved provider configuration, if any.
            locale: Optional locale override when config is unset.
            voice_id: Optional voice id override when config is unset.

        Returns:
            Piper voice id and normalized interview locale.
        """
        if locale is not None:
            resolved_locale = normalize_locale(locale)
        elif config is not None:
            resolved_locale = config.locale
        else:
            resolved_locale = DEFAULT_LOCALE

        if voice_id is not None:
            resolved_voice = normalize_tts_voice_id(voice_id)
        elif locale is not None:
            resolved_voice = default_voice_for_locale(resolved_locale)
        elif config is not None:
            resolved_voice = config.tts_voice_id
        else:
            resolved_voice = default_voice_for_locale(resolved_locale)

        return resolved_voice, resolved_locale

    @staticmethod
    def resolve_for_config(
        config: AppConfig | None,
        *,
        locale: str | None = None,
        voice_id: str | None = None,
    ) -> tuple[PiperVoiceStatusRead, bool]:
        """Build voice status and whether question voice is enabled.

        Args:
            config: Saved provider configuration, if any.
            locale: Optional locale override when config is unset.
            voice_id: Optional voice id override when config is unset.

        Returns:
            Voice status read model and enabled flag for API consumers.
        """
        resolved_voice, resolved_locale = QuestionVoiceStatusService.resolve_tts_target(
            config,
            locale=locale,
            voice_id=voice_id,
        )
        status = PiperVoiceService.get_status(resolved_voice, resolved_locale)
        enabled = config is not None and config.question_voice_enabled
        return status, enabled

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
        if not enabled and status.state == "missing":
            payload["state"] = "unavailable"
        payload["enabled"] = enabled
        return payload
