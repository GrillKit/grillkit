# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for interview feature API handlers."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.ai.base import AIProvider
from app.ai.speech_transcriber import SpeechTranscriber
from app.coding.services.review import CodingReviewService
from app.coding.services.state import CodingStateService
from app.coding.services.submission import CodingSubmissionService
from app.interview.services.completion import SessionCompletionService
from app.interview.services.creation import SessionCreationService
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.known_questions import KnownQuestionsService
from app.interview.services.page import SessionPageService
from app.interview.services.query import InterviewQuery
from app.interview.services.results_page import SessionResultsPageService
from app.platform.api.deps import ConfigServiceDep
from app.platform.services.ai_context import ai_provider_from_config
from app.shared.application.uow_deps import UoWAutoCommitDep, UoWDep
from app.speech.services.transcriber_resolver import (
    resolve_speech_transcriber,
    speech_transcriber_unavailable_message,
)
from app.theory.services.review import TheoryReviewService
from app.theory.services.submission import TheorySubmissionService


async def get_ai_provider() -> AsyncIterator[AIProvider]:
    """Yield a configured AI provider for the lifetime of a request or WebSocket.

    Yields:
        Configured AIProvider instance.

    Raises:
        ValueError: If provider configuration is missing.
    """
    async with ai_provider_from_config() as provider:
        yield provider


def get_interview_query(uow: UoWDep) -> InterviewQuery:
    """Build an interview query service bound to the request unit of work.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Interview query service instance.
    """
    return InterviewQuery(uow)


def get_dashboard_builder(uow: UoWDep) -> DashboardBuilder:
    """Build a dashboard builder bound to the request UoW."""
    return DashboardBuilder(uow)


def get_session_page_service(uow: UoWAutoCommitDep) -> SessionPageService:
    """Build a session page service bound to an auto-commit UoW."""
    return SessionPageService(uow)


def get_session_creation_service(
    uow: UoWAutoCommitDep,
) -> SessionCreationService:
    """Build a session creation service bound to an auto-commit UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Session creation service instance.
    """
    return SessionCreationService(uow)


def get_session_completion_service(
    uow: UoWDep,
) -> SessionCompletionService:
    """Build a session completion service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Session completion service instance.
    """
    return SessionCompletionService(uow)


def get_theory_submission_service(uow: UoWDep) -> TheorySubmissionService:
    """Build a theory submission service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Theory submission service instance.
    """
    return TheorySubmissionService(uow)


def get_coding_submission_service(uow: UoWDep) -> CodingSubmissionService:
    """Build a coding submission service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Coding submission service instance.
    """
    return CodingSubmissionService(uow)


def get_coding_state_service(uow: UoWDep) -> CodingStateService:
    """Build a coding state service bound to the request UoW."""
    return CodingStateService(uow)


def get_known_questions_service(
    uow: UoWAutoCommitDep,
) -> KnownQuestionsService:
    """Build a known questions service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Known questions service instance.
    """
    return KnownQuestionsService(uow)


def get_session_results_page_service(
    uow: UoWDep,
) -> SessionResultsPageService:
    """Build a session results page service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Session results page service instance.
    """
    return SessionResultsPageService(uow)


def get_theory_review_service(uow: UoWDep) -> TheoryReviewService:
    """Build a theory review service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Theory review service instance.
    """
    return TheoryReviewService(uow)


def get_coding_review_service(uow: UoWDep) -> CodingReviewService:
    """Build a coding review service bound to the request UoW.

    Args:
        uow: Application unit of work for the request scope.

    Returns:
        Coding review service instance.
    """
    return CodingReviewService(uow)


InterviewQueryDep = Annotated[InterviewQuery, Depends(get_interview_query)]
DashboardBuilderDep = Annotated[DashboardBuilder, Depends(get_dashboard_builder)]
SessionPageServiceDep = Annotated[
    SessionPageService,
    Depends(get_session_page_service),
]
SessionCreationServiceDep = Annotated[
    SessionCreationService,
    Depends(get_session_creation_service),
]
SessionCompletionServiceDep = Annotated[
    SessionCompletionService,
    Depends(get_session_completion_service),
]
TheorySubmissionServiceDep = Annotated[
    TheorySubmissionService,
    Depends(get_theory_submission_service),
]
CodingSubmissionServiceDep = Annotated[
    CodingSubmissionService,
    Depends(get_coding_submission_service),
]
CodingStateServiceDep = Annotated[
    CodingStateService,
    Depends(get_coding_state_service),
]
KnownQuestionsServiceDep = Annotated[
    KnownQuestionsService,
    Depends(get_known_questions_service),
]
SessionResultsPageServiceDep = Annotated[
    SessionResultsPageService,
    Depends(get_session_results_page_service),
]
TheoryReviewServiceDep = Annotated[
    TheoryReviewService,
    Depends(get_theory_review_service),
]
CodingReviewServiceDep = Annotated[
    CodingReviewService,
    Depends(get_coding_review_service),
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
