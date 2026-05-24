# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Base class for loading ML artifacts into the current process."""

import asyncio
import logging
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class InProcessArtifactRuntime:
    """Hold one loaded artifact and expose load/unload helpers.

    Subclasses implement ``normalize_key``, ``is_installed``, and ``load_sync``.
    """

    _artifact: ClassVar[Any | None] = None
    _loaded_key: ClassVar[str | None] = None
    _load_error: ClassVar[str | None] = None

    @classmethod
    def normalize_key(cls, key: str) -> str:
        """Normalize an artifact identifier to the canonical form."""
        raise NotImplementedError

    @classmethod
    def is_installed(cls, key: str) -> bool:
        """Return whether artifact files are present on disk."""
        raise NotImplementedError

    @classmethod
    def load_sync(cls, key: str) -> Any:
        """Load the artifact from disk (blocking)."""
        raise NotImplementedError

    @classmethod
    def loaded_key(cls) -> str | None:
        """Return the key of the artifact currently in memory, if any."""
        return cls._loaded_key

    @classmethod
    def load_error(cls) -> str | None:
        """Return the last in-process load error message, if any."""
        return cls._load_error

    @classmethod
    def is_loaded(cls, key: str) -> bool:
        """Return whether an artifact for ``key`` is loaded in this process."""
        if cls._artifact is None or cls._loaded_key is None:
            return False
        return cls._loaded_key == cls.normalize_key(key)

    @classmethod
    async def load(cls, key: str) -> bool:
        """Load or reload the artifact for ``key`` from disk.

        Args:
            key: Artifact identifier.

        Returns:
            True if an artifact is loaded for the key after this call.
        """
        code = cls.normalize_key(key)
        if not cls.is_installed(code):
            cls.unload()
            cls._load_error = None
            return False

        try:
            artifact = await asyncio.to_thread(cls.load_sync, code)
        except Exception as exc:
            logger.exception("Failed to load artifact %s", code)
            cls.unload()
            cls._load_error = str(exc)
            return False

        cls._artifact = artifact
        cls._loaded_key = code
        cls._load_error = None
        cls.on_loaded(code, artifact)
        return True

    @classmethod
    def unload(cls) -> None:
        """Drop the in-memory artifact."""
        cls._artifact = None
        cls._loaded_key = None
        cls.on_unloaded()

    @classmethod
    def on_loaded(cls, key: str, artifact: Any) -> None:
        """Hook invoked after a successful load (optional)."""

    @classmethod
    def on_unloaded(cls) -> None:
        """Hook invoked after unload (optional)."""
