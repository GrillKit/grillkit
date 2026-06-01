# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Advance interview sessions to the next unanswered question."""

from typing import Any

from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork


class SessionNavigationService:
    """Shared navigation after a round is completed or timed out."""

    @staticmethod
    def advance_to_next_unanswered(
        uow: InterviewUnitOfWork,
        interview_id: str,
        *,
        question_id: str,
        round_num: int,
    ) -> tuple[dict[str, Any] | None, int | None]:
        """Activate the next unanswered round and build client payload.

        Loads the domain aggregate, finds the next open answer, starts its timer
        when configured, and persists via ``InterviewRepository.save_aggregate``.

        Args:
            uow: Active unit of work.
            interview_id: Parent interview UUID.
            question_id: Question ID of the completed round.
            round_num: Follow-up round that was just completed.

        Returns:
            Tuple of (next_question dict or None, timer_remaining_seconds or None).

        Raises:
            InterviewNotFoundError: If the session does not exist.
            InterviewNotActiveError: If the session is not active.
        """
        aggregate = uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            raise InterviewNotFoundError(interview_id)

        aggregate.ensure_active()

        current_index = next(
            i
            for i, answer in enumerate(aggregate.answers)
            if answer.question_id == question_id and answer.round == round_num
        )
        next_answer = aggregate.find_next_unanswered_after(current_index)
        if next_answer is None:
            return None, None

        updated = aggregate.start_timer_for_answer(next_answer.id)
        uow.interviews.save_aggregate(updated)

        activated = next(answer for answer in updated.answers if answer.id == next_answer.id)
        timer_remaining = activated.remaining_seconds(updated.question_time_limit_seconds)
        return updated.next_question_client_payload(activated), timer_remaining
