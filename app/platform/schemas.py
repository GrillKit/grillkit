# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models and mappers for the platform feature."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.question_voice.schemas import PiperVoiceStatusRead
from app.shared.speech_models import (
    SPEECH_MODEL_BY_SIZE,
    SpeechModelSpec,
)
from app.speech.schemas.status import WhisperModelStatusRead

if TYPE_CHECKING:
    from app.platform.services.config import AppConfig


class AppConfigRead(BaseModel):
    """Saved provider settings for configuration UI templates.

    Attributes:
        provider_type: AI provider adapter id.
        base_url: API endpoint URL.
        model: Model name passed to the provider.
        api_key: API key or mask placeholder when ``mask_secret`` was used.
        timeout: Request timeout in seconds.
        locale: Interview language for AI feedback and voice.
        speech_model_size: Whisper model size for dictation.
        question_voice_enabled: Whether Piper TTS reads questions aloud.
        tts_voice_id: Piper voice id for question audio.
        llm_preset_id: Active catalog model id, if set.
    """

    model_config = ConfigDict(frozen=True)

    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0
    locale: str
    speech_model_size: str
    question_voice_enabled: bool = False
    tts_voice_id: str
    llm_preset_id: str | None = None


class LLMPresetOptionRead(BaseModel):
    """One interview model option in the configuration selector.

    Attributes:
        id: Catalog model id.
        display_name: Human-readable label.
        description: Short description shown in the UI.
        model: Provider model name.
        base_url: OpenAI-compatible base URL.
        api_key_required: Whether the form should require an API key.
        accepts_audio_input: Whether the model supports audio answer submission.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    description: str
    model: str
    base_url: str
    api_key_required: bool
    accepts_audio_input: bool = False


class SpeechModelSpecRead(BaseModel):
    """Whisper model metadata for one size tier on the config page.

    Attributes:
        size: Model size identifier.
        display_name: Human-readable label.
        hf_repo_id: Hugging Face repository id.
        approx_download_mb: Approximate download size in megabytes.
        ram_hint: Suggested RAM for running the model.
        speed_hint: Relative speed expectation.
        quality_hint: Relative transcription quality.
    """

    model_config = ConfigDict(frozen=True)

    size: str
    display_name: str
    hf_repo_id: str
    approx_download_mb: int
    ram_hint: str
    speed_hint: str
    quality_hint: str


class ConfigPageContext(BaseModel):
    """Full Jinja context for ``config.html``.

    Attributes:
        config: Masked provider settings for the form, if configured.
        locales: Supported interview locale codes and labels.
        speech_model_specs: Whisper size options keyed by size slug.
        speech_model_status: Whisper install/load status snapshot.
        speech_model_banner: Whether to show the speech model banner.
        status: Alias for ``speech_model_status`` (legacy template name).
        tts_voice_status: Piper question-voice status snapshot.
        tts_voice_banner: Whether to show the question-voice banner.
        llm_presets: Interview model catalog options.
        selected_llm_preset_id: Active catalog model id.
        error: Optional validation or connection error message.
        message: Optional success or informational message.
    """

    model_config = ConfigDict(frozen=True)

    config: AppConfigRead | None
    locales: dict[str, str]
    speech_model_specs: dict[str, SpeechModelSpecRead]
    speech_model_status: WhisperModelStatusRead | None = None
    speech_model_banner: bool = False
    status: WhisperModelStatusRead | None = None
    tts_voice_status: PiperVoiceStatusRead | None = None
    tts_voice_banner: bool = False
    llm_presets: list[LLMPresetOptionRead] = Field(default_factory=list)
    selected_llm_preset_id: str | None = None
    error: str | None = None
    message: str | None = None


class NewLLMModel(BaseModel):
    """User input for adding a catalog model.

    The stable catalog id is derived from ``display_name`` when the model is
    persisted, so it is not part of the user-supplied input.

    Attributes:
        display_name: Human-readable label shown in the UI.
        base_url: OpenAI-compatible base URL.
        model: Provider model name.
        api_key_required: Whether an API key is required for this endpoint.
        api_key: Optional API key stored with the catalog entry.
        accepts_audio_input: Whether the model supports multimodal audio answers.
    """

    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    display_name: str
    base_url: str
    model: str
    api_key_required: bool = False
    api_key: str | None = None
    accepts_audio_input: bool = False

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Display name is required")
        return value

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if not normalized:
            raise ValueError("Base URL is required")
        return normalized

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        if not value:
            raise ValueError("Model name is required")
        return value

    @field_validator("api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value).strip() or None


def app_config_read_from(
    config: "AppConfig",
    *,
    mask_secret: bool = False,
) -> AppConfigRead:
    """Map a ``AppConfig`` service entity to a template read model.

    Args:
        config: Loaded or submitted provider configuration.
        mask_secret: Whether to mask the API key for display.

    Returns:
        Immutable read model for templates.
    """
    data = config.to_dict(mask_secret=mask_secret)
    return AppConfigRead(
        provider_type=str(data["provider_type"]),
        base_url=str(data["base_url"]),
        model=str(data["model"]),
        api_key=data.get("api_key"),
        timeout=float(data["timeout"]),
        locale=str(data["locale"]),
        speech_model_size=str(data["speech_model_size"]),
        question_voice_enabled=bool(data["question_voice_enabled"]),
        tts_voice_id=str(data["tts_voice_id"]),
        llm_preset_id=data.get("llm_preset_id"),
    )


def speech_model_specs_for_config() -> dict[str, SpeechModelSpecRead]:
    """Build speech model spec read models keyed by size for ``config.html``.

    Returns:
        Dict mapping size slug to read model (matches template iteration).
    """
    return {
        size: speech_model_spec_read_from(spec)
        for size, spec in SPEECH_MODEL_BY_SIZE.items()
    }


def speech_model_spec_read_from(spec: SpeechModelSpec) -> SpeechModelSpecRead:
    """Map a speech model spec to a read model.

    Args:
        spec: Whisper model metadata from speech services.

    Returns:
        Immutable read model for templates.
    """
    return SpeechModelSpecRead(
        size=spec.size,
        display_name=spec.display_name,
        hf_repo_id=spec.hf_repo_id,
        approx_download_mb=spec.approx_download_mb,
        ram_hint=spec.ram_hint,
        speed_hint=spec.speed_hint,
        quality_hint=spec.quality_hint,
    )
