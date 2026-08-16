# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Use case for deleting application configuration and unloading speech runtimes."""

from app.platform.domain.config import ConfigService
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator


class DeleteConfigUseCase:
    """Remove persisted config and unload the in-memory speech runtimes.

    Deleting the configuration and unloading the speech models are tightly
    coupled: once no config remains, no speech model should stay resident. The
    orchestration lives here instead of the HTTP handler.
    """

    def __init__(
        self,
        config_service: type[ConfigService],
        coordinator: SpeechRuntimeCoordinator,
    ) -> None:
        self._config_service: type[ConfigService] = config_service
        self._coordinator: SpeechRuntimeCoordinator = coordinator

    def execute(self) -> None:
        """Delete the persisted configuration and unload speech runtimes."""
        self._config_service.delete_config()
        self._coordinator.unload_all()
