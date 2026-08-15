# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for interview feature API handlers."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException

from app.ai.base import AIProvider
from app.ai.speech_transcriber import SpeechTranscriber
from app.coding.queries.loader import CodingTaskLoader as CodingStateService
from app.coding.queries.review_page import CodingReviewPage as CodingReviewService
from app.coding.use_cases.create_section import CreateCodingSection
from app.coding.use_cases.submit_solution import (
    SubmitCodingSolution as CodingSubmissionService,
)
from app.interview.queries.dashboard import InterviewDashboard
from app.interview.queries.loader import InterviewLoader
from app.interview.queries.results_page import CompletedSessionResults
from app.interview.queries.session_page import ActiveSessionPage
from app.interview.use_cases.complete_session import CompleteInterviewSession
from app.interview.use_cases.create_session import CreateInterviewSession
from app.platform.api.deps import SpeechRuntimeDep
from app.shared.application.uow_deps import UoWAutoCommitDep, UoWDep
from app.shared.infrastructure.gateways.ai_context import ai_provider_from_config
from app.speech.domain.transcriber_resolver import (
    resolve_speech_transcriber,
    speech_transcriber_unavailable_message,
)
from app.theory.queries.review_page import TheoryReviewPage as TheoryReviewService
from app.theory.use_cases.create_section import CreateTheorySection
from app.theory.use_cases.submit_answer import (
    SubmitTheoryAnswer as TheorySubmissionService,
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


def get_interview_query(uow: UoWDep) -> InterviewLoader:
    """Build an interview query service bound to the request unit of work."""
    return InterviewLoader(uow)


def get_dashboard_builder(uow: UoWDep) -> InterviewDashboard:
    """Build a dashboard builder bound to the request UoW."""
    return InterviewDashboard(uow)


def get_session_page_service(uow: UoWAutoCommitDep) -> ActiveSessionPage:
    """Build a session page service bound to an auto-commit UoW."""
    return ActiveSessionPage(uow)


def get_create_theory_section(
    uow: UoWAutoCommitDep,
) -> CreateTheorySection:
    """Build a theory section creation use case."""
    return CreateTheorySection(uow)


def get_create_coding_section(
    uow: UoWAutoCommitDep,
) -> CreateCodingSection:
    """Build a coding section creation use case."""
    return CreateCodingSection(uow)


def get_session_creation_service(
    uow: UoWAutoCommitDep,
    create_theory: Annotated[CreateTheorySection, Depends(get_create_theory_section)],
    create_coding: Annotated[CreateCodingSection, Depends(get_create_coding_section)],
) -> CreateInterviewSession:
    """Build a session creation use case composed from section creators.

    Args:
        uow: Application unit of work for the request scope.
        create_theory: Theory section creation use case.
        create_coding: Coding section creation use case.

    Returns:
        Composed ``CreateInterviewSession`` use case instance.
    """
    return CreateInterviewSession(
        uow,
        create_theory_section=create_theory,
        create_coding_section=create_coding,
    )


def get_session_completion_service(
    uow: UoWDep,
) -> CompleteInterviewSession:
    """Build a session completion use case bound to the request UoW."""
    return CompleteInterviewSession(uow)


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


def get_session_results_page_service(
    uow: UoWDep,
) -> CompletedSessionResults:
    """Build a session results page query bound to the request UoW."""
    return CompletedSessionResults(uow)


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


InterviewLoaderDep = Annotated[InterviewLoader, Depends(get_interview_query)]
InterviewDashboardDep = Annotated[InterviewDashboard, Depends(get_dashboard_builder)]
ActiveSessionPageDep = Annotated[
    ActiveSessionPage,
    Depends(get_session_page_service),
]
CreateSessionDep = Annotated[
    CreateInterviewSession,
    Depends(get_session_creation_service),
]
CompleteSessionDep = Annotated[
    CompleteInterviewSession,
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
CreateTheorySectionDep = Annotated[
    CreateTheorySection,
    Depends(get_create_theory_section),
]
CreateCodingSectionDep = Annotated[
    CreateCodingSection,
    Depends(get_create_coding_section),
]
CompletedSessionResultsDep = Annotated[
    CompletedSessionResults,
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
    coordinator: SpeechRuntimeDep,
) -> SpeechTranscriber:
    """Resolve a loaded speech transcriber through the speech runtime.

    Args:
        coordinator: App-lifetime speech runtime coordinator.

    Returns:
        Loaded speech transcriber.

    Raises:
        HTTPException: When a speech model is not installed or loaded.
    """
    transcriber = await resolve_speech_transcriber(coordinator)
    if transcriber is None:
        raise HTTPException(
            status_code=503,
            detail=speech_transcriber_unavailable_message(coordinator),
        )
    return transcriber


SpeechTranscriberDep = Annotated[SpeechTranscriber, Depends(get_speech_transcriber)]
