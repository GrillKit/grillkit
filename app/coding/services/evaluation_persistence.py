# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Persist coding AI evaluation results and advance sections."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Literal

from app.coding.domain.exceptions import CodingSectionNotFoundError
from app.coding.services.evaluator.models import (
    CodingAnswerEvaluation,
    CodingFollowUpEvaluation,
)
from app.coding.services.events import CodingFeedbackEvent
from app.coding.services.navigation import CodingNavigationService, next_task_payload
from app.interview.repositories.uow import InterviewUnitOfWork


class CodingEvaluationPersistenceService:
    """Save coding evaluation scores and advance timed task rounds."""

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        *,
        navigation: CodingNavigationService | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this workflow.
            navigation: Optional navigation collaborator sharing the same uow.
        """
        self._uow = uow
        self._navigation = navigation or CodingNavigationService(uow)

    @staticmethod
    def _apply_hidden_test_cap(
        evaluation: CodingAnswerEvaluation | CodingFollowUpEvaluation,
        submit_test_summary: dict[str, Any] | None,
    ) -> CodingAnswerEvaluation | CodingFollowUpEvaluation:
        """Cap score and force follow-up when hidden tests failed on submit.

        Args:
            evaluation: Parsed AI evaluation.
            submit_test_summary: Hidden test summary from submit.

        Returns:
            Evaluation with score capped when hidden tests failed.
        """
        if submit_test_summary is None:
            return evaluation
        if submit_test_summary.get("status") == "success":
            return evaluation
        capped_score = min(evaluation.score, 3)
        if isinstance(evaluation, CodingAnswerEvaluation):
            return replace(
                evaluation,
                score=capped_score,
                follow_up_needed=True,
                follow_up_mode=evaluation.follow_up_mode or "code",
            )
        return replace(
            evaluation,
            score=capped_score,
            needs_further_follow_up=True,
            follow_up_mode=evaluation.follow_up_mode or "code",
        )

    def persist(
        self,
        *,
        interview_id: str,
        task_id: str,
        round_num: int,
        order: int,
        evaluation: CodingAnswerEvaluation | CodingFollowUpEvaluation,
        follow_up_needed: bool,
        follow_up_text: str | None,
        follow_up_mode: Literal["code", "explanation"] | None,
        submit_test_summary: dict[str, Any] | None,
        submitted_source_code: str,
    ) -> CodingFeedbackEvent:
        """Save AI evaluation results and build a feedback event.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID for the evaluated round.
            round_num: Follow-up round (0 = initial).
            order: Display order of the task.
            evaluation: Parsed AI evaluation.
            follow_up_needed: Whether to create a follow-up row.
            follow_up_text: Follow-up prompt when applicable.
            follow_up_mode: Composer mode for the follow-up round.
            submit_test_summary: Hidden test summary from submit.
            submitted_source_code: Code submitted for the evaluated round.

        Returns:
            Feedback event for the coding WebSocket client.
        """
        evaluation = self._apply_hidden_test_cap(evaluation, submit_test_summary)
        if (
            isinstance(evaluation, CodingAnswerEvaluation)
            and evaluation.follow_up_needed
            or (
                isinstance(evaluation, CodingFollowUpEvaluation)
                and evaluation.needs_further_follow_up
            )
        ):
            follow_up_needed = True
            follow_up_text = follow_up_text or evaluation.follow_up_question
            follow_up_mode = follow_up_mode or evaluation.follow_up_mode

        next_task_data: dict[str, Any] | None = None
        timer_remaining: int | None = None
        resolved_follow_up_mode = follow_up_mode

        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            raise CodingSectionNotFoundError(interview_id)
        section.ensure_active()

        existing_task = section.find_task(task_id, round_num)
        updated = section.with_evaluation(
            task_id,
            round_num,
            evaluation.score,
            evaluation.feedback,
        ).with_submit_test_summary(
            existing_task.id,
            submit_test_summary,
            source_code=existing_task.submitted_code or submitted_source_code,
        )
        follow_up_round: int | None = None
        if follow_up_needed:
            starter_code = (
                submitted_source_code if resolved_follow_up_mode == "code" else None
            )
            updated, pending = updated.with_follow_up(
                task_id,
                follow_up_text or "",
                starter_code=starter_code,
            )
            follow_up_round = pending.round

        self._uow.coding_sections.save_aggregate(updated)

        if follow_up_needed and follow_up_round is not None:
            self._uow.flush()
            reloaded = self._uow.coding_sections.get_aggregate(interview_id)
            if reloaded is None:
                raise CodingSectionNotFoundError(interview_id)
            follow_up = reloaded.find_task(task_id, follow_up_round)
            timed = reloaded.start_timer_for_task(follow_up.id)
            self._uow.coding_sections.save_aggregate(timed)
            activated = next(task for task in timed.tasks if task.id == follow_up.id)
            timer_remaining = activated.remaining_seconds(timed.task_time_limit_seconds)
            next_task_data = next_task_payload(activated)
        elif not follow_up_needed:
            next_task_data, timer_remaining = (
                self._navigation.advance_to_next_unsubmitted(
                    interview_id,
                    task_id=task_id,
                    round_num=round_num,
                )
            )

        return CodingFeedbackEvent(
            task_id=task_id,
            order=order,
            round=round_num,
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
            follow_up_mode=resolved_follow_up_mode,
            next_task=next_task_data,
            feedback=evaluation.feedback,
            timer_remaining_seconds=timer_remaining,
        )
