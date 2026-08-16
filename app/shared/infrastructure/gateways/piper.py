# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""In-process Piper voice loading and synthesis."""

import asyncio
import gc
import io
import logging
from typing import TYPE_CHECKING
import wave

from app.shared.infrastructure.gateways.piper_storage import (
    is_voice_installed,
    voice_dir,
)
from app.shared.infrastructure.in_process_runtime import InProcessArtifactRuntime
from app.shared.tts_voices import normalize_tts_voice_id

if TYPE_CHECKING:
    from piper import PiperVoice

logger = logging.getLogger(__name__)


class PiperGateway(InProcessArtifactRuntime):
    """Hold a loaded :class:`PiperVoice` for the configured question voice.

    Satisfies the :class:`TtsEngine` protocol, so it can be injected into the
    :class:`SpeechRuntimeCoordinator` as the TTS backend.
    """

    def _normalize_key(self, key: str) -> str:
        """Normalize a Piper voice identifier."""
        return normalize_tts_voice_id(key)

    def _is_installed(self, key: str) -> bool:
        """Return whether a valid Piper voice is on disk for ``key``."""
        return is_voice_installed(key)

    def _load_sync(self, key: str) -> "PiperVoice":
        """Load ``PiperVoice`` from a local voice directory (blocking)."""
        from piper import PiperVoice

        directory = voice_dir(key)
        model_path = directory / f"{key}.onnx"
        config_path = directory / f"{key}.onnx.json"
        return PiperVoice.load(model_path, config_path=config_path)

    def is_installed(self, voice_id: str) -> bool:
        """Return whether a valid Piper voice is on disk for ``voice_id``."""
        return self._is_installed(voice_id)

    def is_loaded(self, voice_id: str) -> bool:
        """Return whether the voice for ``voice_id`` is loaded in memory."""
        return self._has_loaded_key(voice_id)

    async def load_voice(self, voice_id: str) -> bool:
        """Load or reload the Piper voice for ``voice_id`` from disk.

        Args:
            voice_id: Piper voice identifier.

        Returns:
            True if a voice is loaded for the id after this call.
        """
        code = self._normalize_key(voice_id)
        loaded = await self._load(voice_id)
        if loaded:
            logger.info("Loaded Piper voice %s from %s", code, voice_dir(code))
        return loaded

    def on_loaded(self, key: str, artifact: "PiperVoice") -> None:
        """Log successful voice load."""
        del artifact
        logger.debug("Piper voice %s loaded into memory", key)

    def on_unloaded(self) -> None:
        """Log successful voice unload."""
        logger.debug("Piper voice unloaded from memory")
        _ = gc.collect()

    def synthesize_wav_bytes_sync(self, text: str) -> bytes:
        """Synthesize WAV audio for ``text`` using the loaded voice (blocking).

        Args:
            text: Question text snapshot.

        Returns:
            Raw WAV file bytes.

        Raises:
            RuntimeError: When no voice is loaded.
        """
        voice = self._artifact
        if voice is None:
            raise RuntimeError("Piper voice is not loaded")

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return buffer.getvalue()

    async def synthesize_wav_bytes(self, text: str) -> bytes:
        """Synthesize WAV audio for ``text`` in a worker thread.

        Args:
            text: Question text snapshot.

        Returns:
            Raw WAV file bytes.
        """
        return await asyncio.to_thread(self.synthesize_wav_bytes_sync, text)


# Single in-process runtime instance shared by the coordinator and status services.
PiperRuntime = PiperGateway()
