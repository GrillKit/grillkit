# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Advance interview sessions to the next unanswered question."""

from typing import Any

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.services.rules.progress import find_next_unanswered_after
from app.shared.infrastructure.models import Interview


class SessionNavigationService:
    """Shared navigation after a round is completed or timed out."""

    @staticmethod
    def advance_to_next_unanswered(
        uow: InterviewUnitOfWork,
        db_interview: Interview,
        session: InterviewRead,
        *,
        question_id: str,
        round_num: int,
    ) -> tuple[dict[str, Any] | None, int | None]:
        """Activate the next unanswered round and build client payload.

        Args:
            uow: Active unit of work.
            db_interview: Parent interview ORM row.
            session: Immutable session read model.
            question_id: Question ID of the completed round.
            round_num: Follow-up round that was just completed.

        Returns:
            Tuple of (next_question dict or None, timer_remaining_seconds or None).
        """
        from app.interview.services.answer_timer import RoundTimerService

        current_index = next(
            i
            for i, ans in enumerate(session.answers)
            if ans.question_id == question_id and ans.round == round_num
        )
        next_question = find_next_unanswered_after(session, current_index)
        if next_question is None:
            return None, None

        next_answer = next(
            a
            for a in db_interview.answers
            if a.question_id == next_question.question_id
            and a.round == next_question.round
        )
        RoundTimerService.activate_timed_round(uow, db_interview, next_answer)
        next_question_data = {
            "question_id": next_question.question_id,
            "order": next_question.order,
            "question_text": next_question.question_text,
            "question_code": next_question.question_code,
            "round": next_question.round,
        }
        timer_remaining = RoundTimerService.remaining_for_answer(
            db_interview, next_answer
        )
        return next_question_data, timer_remaining
