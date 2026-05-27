from typing import Literal

from pydantic import BaseModel, ConfigDict

PiperVoiceState = Literal["missing", "ready", "downloading", "error", "unavailable"]


class PiperVoiceStatusRead(BaseModel):
    """Runtime status of a Piper voice for one locale.

    Attributes:
        voice_id: Piper voice identifier from provider configuration.
        locale: Interview locale used for status messaging.
        locale_label: Display name for the locale.
        state: Installation or download state.
        percent: Download progress 0–100 when ``state`` is ``downloading``.
        message: User-facing status or error text.
        voice_display_name: Piper voice label for UI.
        loaded_in_memory: True when the voice is loaded in this process.
    """

    model_config = ConfigDict(frozen=True)

    voice_id: str
    locale: str
    locale_label: str
    state: PiperVoiceState
    percent: int
    message: str
    voice_display_name: str
    loaded_in_memory: bool = False


class QuestionVoicePageContext(BaseModel):
    """Keys for config and interview templates for Piper question voice.

    Attributes:
        tts_voice_status: Status snapshot for banners and partials.
        tts_voice_banner: Whether to show the install/load banner.
    """

    model_config = ConfigDict(frozen=True)

    tts_voice_status: PiperVoiceStatusRead | None
    tts_voice_banner: bool
