# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview access helpers for other features' API layers."""

from app.interview.domain.session import AnswerView, InterviewView, interview_view
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Interview


def get_interview_for_dictation(interview_id: str) -> InterviewView | None:
    """Load an interview session for dictation WebSocket handlers.

    Args:
        interview_id: Interview session UUID.

    Returns:
        Interview view with answers, or None when not found.
    """
    interview = InterviewQuery.get_interview(interview_id)
    if interview is None:
        return None
    return interview_view(interview)


def load_interview_or_raise(interview_id: str) -> Interview:
    """Load an interview with answers for cross-feature orchestration.

    Args:
        interview_id: Interview session UUID.

    Returns:
        Interview ORM row with answers loaded.

    Raises:
        InterviewNotFoundError: When the session does not exist.
    """
    return InterviewQuery.get_interview_or_raise(interview_id)


def get_current_unanswered(interview: Interview) -> AnswerView | None:
    """Return the first unanswered answer in display order.

    Args:
        interview: Interview with eager-loaded answers.

    Returns:
        The first unanswered answer view, or None.
    """
    return InterviewQuery.get_current_unanswered(interview)
