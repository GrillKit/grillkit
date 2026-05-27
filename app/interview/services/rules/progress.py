# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Helpers for navigating unanswered questions within an interview session."""

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.shared.exceptions import (
    InterviewNotActiveError,
    UnansweredAnswerNotFoundError,
)


def find_first_unanswered(interview: InterviewRead) -> AnswerRead | None:
    """Return the first unanswered answer in display order.

    Args:
        interview: Interview session read model with answers.

    Returns:
        The first AnswerRead with ``answer_text IS NULL``, or None.
    """
    for answer in interview.answers:
        if answer.answer_text is None:
            return answer
    return None


def find_unanswered_for_question(
    interview: InterviewRead, question_id: str
) -> AnswerRead:
    """Return the unanswered answer row for a question (any follow-up round).

    Args:
        interview: Interview session read model with answers.
        question_id: YAML question ID.

    Returns:
        The first unanswered AnswerRead for that question.

    Raises:
        UnansweredAnswerNotFoundError: If no unanswered answer exists for the question.
    """
    for answer in interview.answers:
        if answer.question_id == question_id and answer.answer_text is None:
            return answer
    raise UnansweredAnswerNotFoundError(interview.id, question_id)


def find_next_unanswered_after(
    interview: InterviewRead, current_index: int
) -> AnswerRead | None:
    """Return the next unanswered answer after a position in the answer list.

    Args:
        interview: Interview session read model with answers.
        current_index: Index of the current answer in ``interview.answers``.

    Returns:
        The next unanswered AnswerRead, or None if none remain.
    """
    for answer in interview.answers[current_index + 1 :]:
        if answer.answer_text is None:
            return answer
    return None


def require_active(interview: InterviewRead) -> None:
    """Ensure the interview accepts new answers.

    Args:
        interview: Loaded interview read model.

    Raises:
        InterviewNotActiveError: If the interview is not in ``active`` status.
    """
    if interview.status != "active":
        raise InterviewNotActiveError(interview.id)
