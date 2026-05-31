# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech model page context builder for HTML templates."""

from app.platform.services.config import AppConfig
from app.speech.schemas.page import SpeechModelPageContext
from app.speech.services.whisper_model import WhisperModelService


class SpeechModelPageService:
    """Build template context for Whisper install/load status."""

    @staticmethod
    def build_page_context(
        config: AppConfig | None,
        whisper_model_service: type[WhisperModelService] = WhisperModelService,
    ) -> SpeechModelPageContext:
        """Build speech model keys shared by config, setup, and interview templates.

        Args:
            config: Saved provider configuration, or None when unset.
            whisper_model_service: Whisper model service class (injectable in tests).

        Returns:
            Frozen page context for templates.
        """
        if config is None:
            return SpeechModelPageContext(
                speech_model_status=None,
                speech_model_banner=False,
                status=None,
            )

        status = whisper_model_service.get_status(
            config.speech_model_size,
            config.locale,
        )
        return SpeechModelPageContext(
            speech_model_status=status,
            speech_model_banner=status.state == "missing",
            status=status,
        )
