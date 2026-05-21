# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for injecting application services into route handlers."""

from typing import Annotated

from fastapi import Depends

from app.services.answer_processing import AnswerProcessingService
from app.services.config import ConfigService
from app.services.interview_completion import InterviewCompletionService
from app.services.interview_creation import InterviewCreationService
from app.services.interview_query import InterviewQuery
from app.services.whisper_model import WhisperModelService


def get_config_service() -> type[ConfigService]:
    """Return the config service class used by API handlers."""
    return ConfigService


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


ConfigServiceDep = Annotated[type[ConfigService], Depends(get_config_service)]
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


def get_whisper_model_service() -> type[WhisperModelService]:
    """Return the Whisper model service class used by API handlers."""
    return WhisperModelService


WhisperModelServiceDep = Annotated[
    type[WhisperModelService],
    Depends(get_whisper_model_service),
]
