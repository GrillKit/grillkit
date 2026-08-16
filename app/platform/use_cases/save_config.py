# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Use case for saving application configuration and syncing speech runtimes."""

from dataclasses import dataclass

from app.platform.domain.config import AppConfig, ConfigService
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator


@dataclass(frozen=True)
class SaveConfigResult:
    """Outcome of saving configuration.

    Attributes:
        saved: Whether the configuration was persisted.
        speech_errors: Load errors for STT/TTS that failed after saving.
    """

    saved: bool = True
    speech_errors: tuple[str, ...] = ()


class SaveConfigUseCase:
    """Persist application config and reload the speech runtimes.

    Saving the config and aligning the in-memory speech runtimes are tightly
    coupled, so the orchestration lives here instead of the HTTP handler. The
    config is always saved even when a speech model fails to load; the caller
    surfaces the collected errors as a warning.
    """

    def __init__(
        self,
        config_service: type[ConfigService],
        coordinator: SpeechRuntimeCoordinator,
    ) -> None:
        self._config_service: type[ConfigService] = config_service
        self._coordinator: SpeechRuntimeCoordinator = coordinator

    async def execute(self, config: AppConfig) -> SaveConfigResult:
        """Save ``config`` and reload speech runtimes.

        Args:
            config: Validated configuration to persist.

        Returns:
            Result with collected speech load errors, if any.
        """
        self._config_service.save_config(config)
        speech_errors = await self._coordinator.reload_after_config_save(config)
        return SaveConfigResult(
            saved=True,
            speech_errors=tuple(speech_errors),
        )
