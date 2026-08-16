# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Protocol for a text-to-speech engine held in memory."""

from typing import Protocol


class TtsEngine(Protocol):
    """Load a voice and synthesize WAV audio.

    The :class:`SpeechRuntimeCoordinator` treats any object satisfying this
    protocol as its TTS backend, so swapping TTS implementations only requires a
    different engine.
    """

    def is_installed(self, voice_id: str) -> bool:
        """Return whether a valid voice for ``voice_id`` is present on disk."""
        ...

    def is_loaded(self, voice_id: str) -> bool:
        """Return whether the voice for ``voice_id`` is currently in memory."""
        ...

    def load_error(self) -> str | None:
        """Return the last load failure message, if any."""
        ...

    def unload(self) -> None:
        """Drop the in-memory voice."""
        ...

    async def load_voice(self, voice_id: str) -> bool:
        """Load or reload the voice for ``voice_id``, returning success."""
        ...

    async def synthesize_wav_bytes(self, text: str) -> bytes:
        """Synthesize WAV bytes for ``text`` using the loaded voice.

        Raises:
            RuntimeError: When no voice is loaded.
        """
        ...
