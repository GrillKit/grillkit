# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Base class for loading ML artifacts into the current process."""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InProcessArtifactRuntime:
    """Hold one loaded artifact and expose load/unload helpers.

    Subclasses implement ``_normalize_key``, ``_is_installed`` and ``_load_sync``,
    and expose public, protocol-named wrappers (e.g. ``is_installed(size)`` or
    ``is_installed(voice_id)``) that delegate to the protected helpers. Each
    instance owns its own in-memory artifact state.
    """

    def __init__(self) -> None:
        """Initialize empty artifact state."""
        self._artifact: Any | None = None
        self._loaded_key: str | None = None
        self._load_error: str | None = None

    def _normalize_key(self, key: str) -> str:
        """Normalize an artifact identifier to the canonical form."""
        raise NotImplementedError

    def _is_installed(self, key: str) -> bool:
        """Return whether artifact files are present on disk."""
        raise NotImplementedError

    def _load_sync(self, key: str) -> Any:
        """Load the artifact from disk (blocking)."""
        raise NotImplementedError

    def loaded_key(self) -> str | None:
        """Return the key of the artifact currently in memory, if any."""
        return self._loaded_key

    def load_error(self) -> str | None:
        """Return the last in-process load error message, if any."""
        return self._load_error

    def _has_loaded_key(self, key: str) -> bool:
        """Return whether an artifact for the canonical ``key`` is loaded in this process."""
        if self._artifact is None or self._loaded_key is None:
            return False
        return self._loaded_key == self._normalize_key(key)

    async def _load(self, key: str) -> bool:
        """Load or reload the artifact for ``key`` from disk.

        Args:
            key: Artifact identifier.

        Returns:
            True if an artifact is loaded for the key after this call.
        """
        code = self._normalize_key(key)
        if not self._is_installed(code):
            self.unload()
            self._load_error = None
            return False

        try:
            artifact = await asyncio.to_thread(self._load_sync, code)
        except Exception as exc:
            logger.exception("Failed to load artifact %s", code)
            self.unload()
            self._load_error = str(exc)
            return False

        self._artifact = artifact
        self._loaded_key = code
        self._load_error = None
        self.on_loaded(code, artifact)
        return True

    def unload(self) -> None:
        """Drop the in-memory artifact."""
        self._artifact = None
        self._loaded_key = None
        self.on_unloaded()

    def on_loaded(self, key: str, artifact: Any) -> None:
        """Hook invoked after a successful load (optional)."""

    def on_unloaded(self) -> None:
        """Hook invoked after unload (optional)."""
