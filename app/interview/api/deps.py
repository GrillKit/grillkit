# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for interview feature API handlers."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.ai.base import AIProvider
from app.interview.services.answer_processing import AnswerProcessingService
from app.interview.services.completion import InterviewCompletionService
from app.interview.services.creation import InterviewCreationService
from app.interview.services.query import InterviewQuery
from app.platform.services.ai_context import ai_provider_from_config


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


def get_answer_processing_service() -> type[AnswerProcessingService]:
    """Return the answer processing service class used by API handlers."""
    return AnswerProcessingService


def get_interview_completion_service() -> type[InterviewCompletionService]:
    """Return the interview completion service class used by API handlers."""
    return InterviewCompletionService


InterviewQueryDep = Annotated[type[InterviewQuery], Depends(get_interview_query)]
InterviewCreationServiceDep = Annotated[
    type[InterviewCreationService],
    Depends(get_interview_creation_service),
]
AnswerProcessingServiceDep = Annotated[
    type[AnswerProcessingService],
    Depends(get_answer_processing_service),
]
InterviewCompletionServiceDep = Annotated[
    type[InterviewCompletionService],
    Depends(get_interview_completion_service),
]
AIProviderDep = Annotated[AIProvider, Depends(get_ai_provider)]
