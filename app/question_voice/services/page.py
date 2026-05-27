# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-voice page context builder for HTML templates."""

from app.platform.services.config import AppConfig
from app.question_voice.schemas import PiperVoiceStatusRead, QuestionVoicePageContext
from app.question_voice.services.status import QuestionVoiceStatusService


class QuestionVoicePageService:
    """Build template context for Piper question-voice status."""

    @staticmethod
    def _show_voice_banner(status: PiperVoiceStatusRead) -> bool:
        """Return whether the interview page should show a question-voice banner."""
        if status.state in ("missing", "error", "downloading"):
            return True
        return status.state == "ready" and not status.loaded_in_memory

    @staticmethod
    async def build_page_context(
        config: AppConfig | None,
    ) -> QuestionVoicePageContext:
        """Build Piper voice status keys for config and interview templates.

        Args:
            config: Saved provider configuration, or None when unset.

        Returns:
            Frozen page context for templates.
        """
        if config is None or not config.question_voice_enabled:
            return QuestionVoicePageContext(
                tts_voice_status=None,
                tts_voice_banner=False,
            )

        status, _enabled = QuestionVoiceStatusService.resolve_for_config(config)
        return QuestionVoicePageContext(
            tts_voice_status=status,
            tts_voice_banner=QuestionVoicePageService._show_voice_banner(status),
        )
