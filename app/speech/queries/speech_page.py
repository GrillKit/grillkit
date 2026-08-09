# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech model page context builder for HTML templates."""

from app.platform.domain.config import AppConfig
from app.shared.infrastructure.gateways.whisper_model import WhisperModelService
from app.shared.locales import DEFAULT_LOCALE
from app.shared.speech_models import DEFAULT_SPEECH_MODEL_SIZE
from app.speech.schemas.page import SpeechModelPageContext


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
        size = config.speech_model_size if config else DEFAULT_SPEECH_MODEL_SIZE
        locale = config.locale if config else DEFAULT_LOCALE
        status = whisper_model_service.get_status(size, locale)
        return SpeechModelPageContext(
            speech_model_status=status,
            speech_model_banner=status.state == "missing",
            status=status,
        )
