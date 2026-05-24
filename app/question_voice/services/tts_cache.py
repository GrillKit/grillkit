# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Disk cache for synthesized question audio."""

import hashlib
from pathlib import Path
import re

from app.paths import TTS_CACHE_DIR
from app.question_voice.domain.tts_exceptions import QuestionVoiceSynthesisError
from app.question_voice.services.piper_runtime import PiperRuntime
from app.question_voice.services.piper_storage import is_voice_installed
from app.shared.domain.locales import normalize_locale

_WHITESPACE_RE = re.compile(r"\s+")
_CACHE_VERSION = "v2"


class TtsCacheService:
    """Store and retrieve WAV files under ``data/tts-cache/v2/{locale}/``."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Collapse whitespace for stable cache keys.

        Args:
            text: Raw question text snapshot.

        Returns:
            Normalized text used for hashing.
        """
        return _WHITESPACE_RE.sub(" ", text.strip())

    @staticmethod
    def cache_path(locale: str, text: str) -> Path:
        """Build the on-disk path for a cached WAV file.

        Args:
            locale: Interview locale code.
            text: Question text snapshot.

        Returns:
            Path to ``{sha256}.wav`` under the locale directory.
        """
        code = normalize_locale(locale)
        digest = hashlib.sha256(
            TtsCacheService.normalize_text(text).encode("utf-8")
        ).hexdigest()
        return TTS_CACHE_DIR / _CACHE_VERSION / code / f"{digest}.wav"

    @staticmethod
    async def get_or_fetch(voice_id: str, locale: str, text: str) -> Path:
        """Return a cached WAV path, synthesizing on miss.

        Args:
            voice_id: Piper voice id from provider configuration.
            locale: Interview locale code.
            text: Question text snapshot.

        Returns:
            Path to an existing or newly written WAV file.

        Raises:
            QuestionVoiceSynthesisError: When the voice is missing or synthesis fails.
        """
        path = TtsCacheService.cache_path(locale, text)
        if path.is_file():
            return path

        if not is_voice_installed(voice_id):
            raise QuestionVoiceSynthesisError(
                "Question voice is not installed. Download it on the Configuration page."
            )

        if not PiperRuntime.is_loaded(voice_id):
            loaded = await PiperRuntime.load_voice(voice_id)
            if not loaded:
                detail = PiperRuntime.load_error() or "Could not load question voice."
                raise QuestionVoiceSynthesisError(detail)

        try:
            audio = await PiperRuntime.synthesize_wav_bytes(text)
        except Exception as exc:
            raise QuestionVoiceSynthesisError("TTS synthesis failed.") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        return path
