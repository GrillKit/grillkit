# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for platform (config) API handlers."""

from typing import Annotated

from fastapi import Depends, Request

from app.platform.domain.config import ConfigService
from app.platform.domain.llm_catalog import LLMCatalogService
from app.platform.domain.speech_runtime import SpeechRuntimeCoordinator
from app.platform.use_cases.add_llm_model import AddLLMModelUseCase
from app.platform.use_cases.delete_config import DeleteConfigUseCase
from app.platform.use_cases.save_config import SaveConfigUseCase


def get_config_service() -> type[ConfigService]:
    """Return the config service class used by API handlers."""
    return ConfigService


ConfigServiceDep = Annotated[type[ConfigService], Depends(get_config_service)]


def get_add_llm_model_use_case() -> AddLLMModelUseCase:
    """Return the add-model use case wired with its services."""
    return AddLLMModelUseCase(
        config_service=ConfigService,
        llm_catalog_service=LLMCatalogService,
    )


AddLLMModelUseCaseDep = Annotated[
    AddLLMModelUseCase,
    Depends(get_add_llm_model_use_case),
]


def get_save_config_use_case(request: Request) -> SaveConfigUseCase:
    """Return the save-config use case wired with app-lifetime services."""
    return SaveConfigUseCase(
        config_service=ConfigService,
        coordinator=request.app.state.speech_runtime,
    )


SaveConfigUseCaseDep = Annotated[
    SaveConfigUseCase,
    Depends(get_save_config_use_case),
]


def get_delete_config_use_case(request: Request) -> DeleteConfigUseCase:
    """Return the delete-config use case wired with app-lifetime services."""
    return DeleteConfigUseCase(
        config_service=ConfigService,
        coordinator=request.app.state.speech_runtime,
    )


DeleteConfigUseCaseDep = Annotated[
    DeleteConfigUseCase,
    Depends(get_delete_config_use_case),
]


def get_speech_runtime(request: Request) -> SpeechRuntimeCoordinator:
    """Return the app-lifetime speech runtime coordinator."""
    return request.app.state.speech_runtime


SpeechRuntimeDep = Annotated[
    SpeechRuntimeCoordinator,
    Depends(get_speech_runtime),
]
