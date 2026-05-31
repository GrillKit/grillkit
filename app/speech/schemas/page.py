# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Template page context for speech model status."""

from pydantic import BaseModel, ConfigDict

from app.speech.schemas.status import WhisperModelStatusRead


class SpeechModelPageContext(BaseModel):
    """Keys shared by config, setup, and interview templates for Whisper status.

    Attributes:
        speech_model_status: Status snapshot for banners and partials.
        speech_model_banner: Whether to show the install/download banner.
        status: Alias for ``speech_model_status`` (legacy template name).
    """

    model_config = ConfigDict(frozen=True)

    speech_model_status: WhisperModelStatusRead | None
    speech_model_banner: bool
    status: WhisperModelStatusRead | None = None
