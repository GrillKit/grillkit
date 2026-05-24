# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared status resolution for disk-cached ML artifacts."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.shared.infrastructure.artifact_download import ArtifactDownloadService

ArtifactStatusState = Literal["missing", "ready", "downloading", "error"]


@dataclass(frozen=True)
class BuiltArtifactStatus:
    """Resolved install/load state for one artifact key.

    Attributes:
        state: Installation or download state.
        percent: Download progress 0–100 when downloading.
        message: User-facing status or error text.
        loaded_in_memory: True when the runtime has loaded the artifact.
    """

    state: ArtifactStatusState
    percent: int
    message: str
    loaded_in_memory: bool = False


class ArtifactStatusBuilder:
    """Build artifact status snapshots from shared download and runtime checks."""

    @staticmethod
    def build(
        *,
        key: str,
        service: type[ArtifactDownloadService],
        is_installed: Callable[[], bool],
        is_loaded: Callable[[], bool],
        load_error: Callable[[], str | None],
        downloading_message: str,
        missing_message: str,
        ready_loaded_message: str,
        ready_loading_message: str,
        ready_load_failed_message: Callable[[str], str],
    ) -> BuiltArtifactStatus:
        """Resolve status for one artifact using download and runtime callbacks.

        Args:
            key: Artifact identifier (model size, voice id, etc.).
            service: Download service class for this artifact family.
            is_installed: Return whether files exist on disk.
            is_loaded: Return whether the in-process runtime is loaded.
            load_error: Return runtime load error text, if any.
            downloading_message: Message while a download is active.
            missing_message: Message when files are not installed.
            ready_loaded_message: Message when installed and loaded.
            ready_loading_message: Message when installed but not yet loaded.
            ready_load_failed_message: Build message when install succeeded but load failed.

        Returns:
            Built status for mapping to feature-specific dataclasses.
        """
        error_message = service.active_download_error(key)
        if error_message is not None:
            return BuiltArtifactStatus("error", 0, error_message)

        if service.is_downloading(key):
            return BuiltArtifactStatus(
                "downloading",
                service.download_percent(),
                downloading_message,
            )

        if is_installed():
            loaded = is_loaded()
            runtime_error = load_error()
            if loaded:
                message = ready_loaded_message
            elif runtime_error:
                message = ready_load_failed_message(runtime_error)
            else:
                message = ready_loading_message
            return BuiltArtifactStatus("ready", 100, message, loaded_in_memory=loaded)

        return BuiltArtifactStatus("missing", 0, missing_message)
