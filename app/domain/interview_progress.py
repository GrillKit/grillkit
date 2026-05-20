# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pure helpers for navigating unanswered questions within an interview."""

from app.domain.exceptions import InterviewNotActiveError, UnansweredAnswerNotFoundError
from app.models import Answer, Interview


def find_first_unanswered(interview: Interview) -> Answer | None:
    """Return the first unanswered answer in display order.

    Args:
        interview: Interview with eager-loaded answers.

    Returns:
        The first Answer with ``answer_text IS NULL``, or None.
    """
    for answer in interview.answers:
        if answer.answer_text is None:
            return answer
    return None


def find_unanswered_for_question(interview: Interview, question_id: str) -> Answer:
    """Return the unanswered answer row for a question (any follow-up round).

    Args:
        interview: Interview with eager-loaded answers.
        question_id: YAML question ID.

    Returns:
        The first unanswered Answer for that question.

    Raises:
        UnansweredAnswerNotFoundError: If no unanswered answer exists for the question.
    """
    for answer in interview.answers:
        if answer.question_id == question_id and answer.answer_text is None:
            return answer
    raise UnansweredAnswerNotFoundError(interview.id, question_id)


def find_next_unanswered_after(
    interview: Interview, current_index: int
) -> Answer | None:
    """Return the next unanswered answer after a position in the answer list.

    Args:
        interview: Interview with eager-loaded answers.
        current_index: Index of the current answer in ``interview.answers``.

    Returns:
        The next unanswered Answer, or None if none remain.
    """
    for answer in interview.answers[current_index + 1 :]:
        if answer.answer_text is None:
            return answer
    return None


def require_active(interview: Interview) -> None:
    """Ensure the interview accepts new answers.

    Args:
        interview: Loaded interview instance.

    Raises:
        InterviewNotActiveError: If the interview is not in ``active`` status.
    """
    if interview.status != "active":
        raise InterviewNotActiveError(interview.id)
