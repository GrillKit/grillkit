# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview access helpers for cross-feature services."""

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.query import InterviewQuery


def get_interview_for_dictation(interview_id: str) -> InterviewRead | None:
    """Load an interview session for dictation WebSocket handlers.

    Args:
        interview_id: Interview session UUID.

    Returns:
        Interview read model with answers, or None when not found.
    """
    return InterviewQuery.get_interview(interview_id)


def load_interview_or_raise(interview_id: str) -> InterviewRead:
    """Load an interview with answers for cross-feature orchestration.

    Args:
        interview_id: Interview session UUID.

    Returns:
        Interview read model with answers loaded.

    Raises:
        InterviewNotFoundError: When the session does not exist.
    """
    return InterviewQuery.get_interview_or_raise(interview_id)


def get_current_unanswered(interview: InterviewRead) -> AnswerRead | None:
    """Return the first unanswered answer in display order.

    Args:
        interview: Interview read model with answers.

    Returns:
        The first unanswered answer read model, or None.
    """
    return InterviewQuery.get_current_unanswered(interview)
