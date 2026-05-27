# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration service module.

This module provides service layer for managing application settings
stored in data/config.json and LLM selection via data/llm_models.json.
"""

from dataclasses import dataclass, replace
import json
from typing import Any

from app.ai.base import AIProvider
from app.ai.factory import ProviderFactory
from app.paths import CONFIG_PATH, DATA_DIR
from app.platform.services.llm_catalog import LLMCatalogService
from app.question_voice.services.rules.voices import (
    DEFAULT_TTS_VOICE_ID,
    default_voice_for_locale,
    normalize_tts_voice_id,
)
from app.shared.locales import DEFAULT_LOCALE, normalize_locale
from app.speech.services.rules.speech_models import (
    DEFAULT_SPEECH_MODEL_SIZE,
    normalize_speech_model_size,
)

MASKED_API_KEY_PLACEHOLDER = "***"


@dataclass
class AppConfig:
    """Runtime provider and application configuration.

    LLM endpoint details are loaded from ``data/llm_models.json``.
    ``config.json`` stores application settings only.

    Attributes:
        provider_type: Type of AI provider (e.g., "openai-compatible").
        base_url: API endpoint URL.
        model: Model name to use.
        api_key: API key for authentication (optional for local providers).
        timeout: Request timeout in seconds.
        locale: Interview language for AI feedback and voice input.
        speech_model_size: Whisper model size for offline dictation.
        question_voice_enabled: Read interview questions aloud when TTS is available.
        tts_voice_id: Piper voice id for question audio synthesis.
        llm_preset_id: Active catalog model id from ``llm_models.json``.
    """

    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0
    locale: str = DEFAULT_LOCALE
    speech_model_size: str = DEFAULT_SPEECH_MODEL_SIZE
    question_voice_enabled: bool = False
    tts_voice_id: str = DEFAULT_TTS_VOICE_ID
    llm_preset_id: str | None = None

    def to_dict(self, mask_secret: bool = False) -> dict[str, Any]:
        """Convert to dictionary for UI display.

        Args:
            mask_secret: If True, mask api_key as "***".

        Returns:
            Dictionary representation of the configuration.
        """
        return {
            **self._shared_fields(),
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self._serialized_api_key(mask_secret),
            "llm_preset_id": self.llm_preset_id,
        }

    def to_storage_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence in ``config.json``.

        Returns:
            Application settings only.
        """
        return self._shared_fields()

    def _shared_fields(self) -> dict[str, Any]:
        """Return application settings persisted in ``config.json``."""
        return {
            "timeout": self.timeout,
            "locale": self.locale,
            "speech_model_size": self.speech_model_size,
            "question_voice_enabled": self.question_voice_enabled,
            "tts_voice_id": self.tts_voice_id,
        }

    def _serialized_api_key(self, mask_secret: bool) -> str | None:
        """Serialize api_key for UI output."""
        if mask_secret and self.api_key:
            return MASKED_API_KEY_PLACEHOLDER
        return self.api_key

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """Create from ``config.json`` application settings.

        Args:
            data: Dictionary with configuration values.

        Returns:
            AppConfig instance without LLM fields populated yet.
        """
        locale = normalize_locale(data.get("locale", DEFAULT_LOCALE))
        raw_voice_id = data.get("tts_voice_id")
        if raw_voice_id:
            tts_voice_id = normalize_tts_voice_id(str(raw_voice_id))
        else:
            tts_voice_id = default_voice_for_locale(locale)
        return cls(
            provider_type="openai-compatible",
            base_url="",
            model="",
            timeout=data.get("timeout", 60.0),
            locale=locale,
            speech_model_size=normalize_speech_model_size(
                data.get("speech_model_size", DEFAULT_SPEECH_MODEL_SIZE)
            ),
            question_voice_enabled=bool(data.get("question_voice_enabled", False)),
            tts_voice_id=tts_voice_id,
        )

    @staticmethod
    def resolve_api_key_from_form(
        submitted: str,
        preset_id: str,
    ) -> str | None:
        """Use a new API key from the form or keep the stored catalog key.

        Args:
            submitted: Raw ``api_key`` form value (may be empty or the mask placeholder).
            preset_id: Selected catalog model id.

        Returns:
            New key from the form, stored catalog key when blank, or ``None``.
        """
        value = submitted.strip()
        if value and value != MASKED_API_KEY_PLACEHOLDER:
            return value
        entry = LLMCatalogService.get_model(preset_id)
        if entry and entry.api_key:
            return entry.api_key
        return None

    def effective(self) -> "AppConfig":
        """Return configuration with catalog defaults and runtime overrides applied.

        Returns:
            Copy of this config ready for provider creation and connection tests.
        """
        return ConfigService.resolve_effective_config(self)


class ConfigService:
    """Service for managing provider configuration."""

    @staticmethod
    def get_config() -> AppConfig | None:
        """Load configuration from disk.

        Returns:
            AppConfig if ``config.json`` exists, None otherwise.
        """
        if not CONFIG_PATH.exists():
            return None
        data = json.loads(CONFIG_PATH.read_text())
        app_config = AppConfig.from_dict(data)
        selected_id = LLMCatalogService.get_selected_model_id()
        if selected_id is None:
            return app_config
        app_config = replace(app_config, llm_preset_id=selected_id)
        if LLMCatalogService.get_model(selected_id) is not None:
            app_config = ConfigService.resolve_effective_config(app_config)
        return app_config

    @staticmethod
    def resolve_effective_config(config: AppConfig) -> AppConfig:
        """Apply catalog entry fields to a configuration copy.

        Args:
            config: Stored or submitted provider configuration.

        Returns:
            Configuration ready for provider creation and connection tests.
        """
        entry = LLMCatalogService.get_model(config.llm_preset_id)
        if entry is None:
            raise ValueError("No interview model selected")
        api_key = entry.api_key or config.api_key
        return replace(
            config,
            provider_type=entry.provider_type,
            model=entry.model,
            base_url=entry.base_url,
            api_key=api_key,
        )

    @staticmethod
    def save_config(config: AppConfig) -> None:
        """Save application settings and LLM selection.

        Args:
            config: Configuration to save.
        """
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if config.llm_preset_id:
            LLMCatalogService.save_model_selection(config.llm_preset_id, config.api_key)
        CONFIG_PATH.write_text(json.dumps(config.to_storage_dict(), indent=2))

    @staticmethod
    def delete_config() -> None:
        """Remove configuration file."""
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()

    @staticmethod
    async def test_connection(config: AppConfig) -> tuple[bool, str]:
        """Test provider connection without saving.

        Args:
            config: Configuration to test.

        Returns:
            Tuple of (success: bool, message: str).
        """
        try:
            effective = config.effective()
            provider = ProviderFactory.from_config(
                api_type=effective.provider_type,
                base_url=effective.base_url,
                model=effective.model,
                api_key=effective.api_key,
                timeout=effective.timeout,
            )
            is_valid = await provider.validate()
            if is_valid:
                return True, "Connection successful"
            return False, "Invalid API key or unreachable endpoint"
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {e}"

    @staticmethod
    def create_provider_from_config() -> AIProvider:
        """Create AI provider from saved configuration.

        Returns:
            Configured AI provider instance.

        Raises:
            ValueError: If no configuration exists.
        """
        config = ConfigService.get_config()
        if not config:
            raise ValueError("No configuration found")
        effective = config.effective()
        return ProviderFactory.from_config(
            api_type=effective.provider_type,
            base_url=effective.base_url,
            model=effective.model,
            api_key=effective.api_key,
            timeout=effective.timeout,
        )
