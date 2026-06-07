# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for interview feature API handlers."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.ai.base import AIProvider
from app.ai.speech_transcriber import SpeechTranscriber
from app.interview.services.completion import InterviewCompletionService
from app.interview.services.creation import InterviewCreationService
from app.interview.services.query import InterviewQuery
from app.platform.api.deps import ConfigServiceDep
from app.platform.services.ai_context import ai_provider_from_config
from app.speech.services.transcriber_resolver import (
    resolve_speech_transcriber,
    speech_transcriber_unavailable_message,
)


async def get_ai_provider() -> AsyncIterator[AIProvider]:
    """Yield a configured AI provider for the lifetime of a request or WebSocket.

    Yields:
        Configured AIProvider instance.

    Raises:
        ValueError: If provider configuration is missing.
    """
    async with ai_provider_from_config() as provider:
        yield provider


def get_interview_query() -> type[InterviewQuery]:
    """Return the interview query service class used by API handlers."""
    return InterviewQuery


def get_interview_creation_service() -> type[InterviewCreationService]:
    """Return the interview creation service class used by API handlers."""
    return InterviewCreationService


def get_interview_completion_service() -> type[InterviewCompletionService]:
    """Return the interview completion service class used by API handlers."""
    return InterviewCompletionService


InterviewQueryDep = Annotated[type[InterviewQuery], Depends(get_interview_query)]
InterviewCreationServiceDep = Annotated[
    type[InterviewCreationService],
    Depends(get_interview_creation_service),
]
InterviewCompletionServiceDep = Annotated[
    type[InterviewCompletionService],
    Depends(get_interview_completion_service),
]
AIProviderDep = Annotated[AIProvider, Depends(get_ai_provider)]


async def get_speech_transcriber(
    request: Request,
    config_service: ConfigServiceDep,
) -> SpeechTranscriber:
    """Resolve a loaded Whisper transcriber from application state.

    Args:
        request: FastAPI request with ASGI app state.
        config_service: Provider configuration service.

    Returns:
        Loaded speech transcriber.

    Raises:
        HTTPException: When Whisper is not installed or loaded.
    """
    transcriber = await resolve_speech_transcriber(request.app, config_service)
    if transcriber is None:
        raise HTTPException(
            status_code=503,
            detail=speech_transcriber_unavailable_message(),
        )
    return transcriber


SpeechTranscriberDep = Annotated[SpeechTranscriber, Depends(get_speech_transcriber)]
