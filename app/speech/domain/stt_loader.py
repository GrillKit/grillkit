# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Protocol for loading a speech-to-text model into memory."""

from typing import Protocol

from app.ai.speech_transcriber import SpeechTranscriber


class SttModelLoader(Protocol):
    """Load and hold a single in-memory :class:`SpeechTranscriber`.

    A loader is the concrete bridge between a vendor's model (e.g. faster-whisper)
    and the rest of the application. The :class:`SpeechRuntimeCoordinator` treats
    any object satisfying this protocol as its STT backend, so swapping STT
    implementations only requires a different loader.
    """

    def is_installed(self, size: str) -> bool:
        """Return whether a valid model for ``size`` is present on disk."""
        ...

    def is_loaded(self, size: str) -> bool:
        """Return whether the model for ``size`` is currently in memory."""
        ...

    def load_error(self) -> str | None:
        """Return the last load failure message, if any."""
        ...

    def unload(self) -> None:
        """Drop the in-memory model."""
        ...

    async def load_size(self, size: str) -> bool:
        """Load or reload the model for ``size``, returning success."""
        ...

    def get(self) -> SpeechTranscriber | None:
        """Return the currently loaded transcriber, if any."""
        ...
