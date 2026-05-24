# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared in-process download state for disk-cached ML artifacts."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import ClassVar

logger = logging.getLogger(__name__)


class ArtifactDownloadService:
    """Download lock, progress, and background task orchestration for artifacts.

    Subclasses must redefine the ``ClassVar`` state fields below so Whisper,
    Piper, and other artifacts do not share one download lock or progress.
    """

    _download_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _active_key: ClassVar[str | None] = None
    _percent: ClassVar[int] = 0
    _error_key: ClassVar[str | None] = None
    _error_message: ClassVar[str | None] = None

    @classmethod
    def reset_download_state(cls) -> None:
        """Clear in-memory download progress (for tests)."""
        cls._active_key = None
        cls._percent = 0
        cls._error_key = None
        cls._error_message = None

    @classmethod
    def active_download_error(cls, key: str) -> str | None:
        """Return a stored error message for ``key`` when no download is active."""
        if (
            cls._error_key == key
            and cls._error_message is not None
            and cls._active_key is None
        ):
            return cls._error_message
        return None

    @classmethod
    def is_downloading(cls, key: str) -> bool:
        """Return whether ``key`` is the artifact currently being downloaded."""
        return cls._active_key == key

    @classmethod
    def download_percent(cls) -> int:
        """Return the current download percent for the active artifact."""
        return cls._percent

    @classmethod
    def set_download_percent(cls, percent: int) -> None:
        """Update in-memory download percent from progress callbacks."""
        cls._percent = percent

    @classmethod
    async def schedule_download(
        cls,
        key: str,
        runner: Callable[[str], Awaitable[None]],
    ) -> bool:
        """Start a background download when none is already active.

        Args:
            key: Artifact identifier (size, voice id, etc.).
            runner: Async callable that performs install and load.

        Returns:
            True when a new download task was scheduled.
        """
        async with cls._download_lock:
            if cls._active_key is not None:
                return False
            cls._active_key = key
            cls._percent = 0
            cls._error_key = None
            cls._error_message = None

        asyncio.create_task(cls._run_download_task(key, runner))
        return True

    @classmethod
    async def _run_download_task(
        cls,
        key: str,
        runner: Callable[[str], Awaitable[None]],
    ) -> None:
        """Execute ``runner`` and update shared error/active state."""
        try:
            await runner(key)
            cls.clear_download_error()
        except Exception as exc:
            logger.exception("Artifact download failed for %s", key)
            cls.record_download_error(key, str(exc))
        finally:
            async with cls._download_lock:
                cls._active_key = None
                cls._percent = 0

    @classmethod
    def record_download_error(cls, key: str, message: str) -> None:
        """Store the last download failure for status reporting."""
        cls._error_key = key
        cls._error_message = message

    @classmethod
    def clear_download_error(cls) -> None:
        """Clear the last download error after a successful install."""
        cls._error_key = None
        cls._error_message = None
