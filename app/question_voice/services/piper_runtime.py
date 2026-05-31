# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""In-process Piper voice loading and synthesis."""

import asyncio
import io
import logging
from typing import TYPE_CHECKING
import wave

from app.question_voice.services.piper_storage import is_voice_installed, voice_dir
from app.question_voice.services.rules.voices import normalize_tts_voice_id
from app.shared.infrastructure.in_process_runtime import InProcessArtifactRuntime

if TYPE_CHECKING:
    from piper import PiperVoice

logger = logging.getLogger(__name__)


class PiperRuntime(InProcessArtifactRuntime):
    """Hold the loaded :class:`PiperVoice` for the configured question voice."""

    @classmethod
    def normalize_key(cls, key: str) -> str:
        """Normalize a Piper voice identifier."""
        return normalize_tts_voice_id(key)

    @classmethod
    def is_installed(cls, key: str) -> bool:
        """Return whether a valid Piper voice is on disk for ``key``."""
        return is_voice_installed(key)

    @classmethod
    def load_sync(cls, key: str) -> "PiperVoice":
        """Load ``PiperVoice`` from a local voice directory (blocking)."""
        from piper import PiperVoice

        directory = voice_dir(key)
        model_path = directory / f"{key}.onnx"
        config_path = directory / f"{key}.onnx.json"
        return PiperVoice.load(model_path, config_path=config_path)

    @classmethod
    async def load_voice(cls, voice_id: str) -> bool:
        """Load or reload the Piper voice for ``voice_id`` from disk.

        Args:
            voice_id: Piper voice identifier.

        Returns:
            True if a voice is loaded for the id after this call.
        """
        code = cls.normalize_key(voice_id)
        loaded = await cls.load(voice_id)
        if loaded:
            logger.info("Loaded Piper voice %s from %s", code, voice_dir(code))
        return loaded

    @classmethod
    def on_loaded(cls, key: str, artifact: "PiperVoice") -> None:
        """Log successful voice load."""
        del artifact
        logger.debug("Piper voice %s loaded into memory", key)

    @classmethod
    def synthesize_wav_bytes_sync(cls, text: str) -> bytes:
        """Synthesize WAV audio for ``text`` using the loaded voice (blocking).

        Args:
            text: Question text snapshot.

        Returns:
            Raw WAV file bytes.

        Raises:
            RuntimeError: When no voice is loaded.
        """
        voice = cls._artifact
        if voice is None:
            raise RuntimeError("Piper voice is not loaded")

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return buffer.getvalue()

    @classmethod
    async def synthesize_wav_bytes(cls, text: str) -> bytes:
        """Synthesize WAV audio for ``text`` in a worker thread.

        Args:
            text: Question text snapshot.

        Returns:
            Raw WAV file bytes.
        """
        return await asyncio.to_thread(cls.synthesize_wav_bytes_sync, text)
