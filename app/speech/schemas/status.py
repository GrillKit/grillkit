# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Whisper model status read models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

WhisperModelState = Literal["missing", "ready", "downloading", "error"]


class WhisperModelStatusRead(BaseModel):
    """Runtime status of the Whisper model for one size and locale.

    Attributes:
        size: Speech model size identifier.
        locale: Interview locale used for transcription language.
        locale_label: Display name for the locale.
        state: Installation or download state.
        percent: Download progress 0–100 when ``state`` is ``downloading``.
        message: User-facing status or error text.
        model_display_name: Whisper package label for UI.
        loaded_in_memory: True when the model is loaded for this size.
    """

    model_config = ConfigDict(frozen=True)

    size: str
    locale: str
    locale_label: str
    state: WhisperModelState
    percent: int
    message: str
    model_display_name: str
    loaded_in_memory: bool = False
