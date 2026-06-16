# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding task submit orchestration for the coding WebSocket."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from app.ai.base import AIProvider
from app.coding.domain.exceptions import (
    CodingSectionNotFoundError,
    CodingTaskNotCurrentError,
    CodingTaskTimerError,
)
from app.coding.services.evaluation_persistence import (
    CodingEvaluationPersistenceService,
)
from app.coding.services.evaluator.service import CodingEvaluatorService
from app.coding.services.events import CodingFeedbackEvent
from app.coding.services.navigation import CodingNavigationService
from app.coding.services.run_execution import coding_run_result_to_summary
from app.coding.services.runner import CodingRunnerService
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.events import (
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewEvent,
)
from app.interview.services.rules.feedback import timeout_feedback_for_locale


@dataclass(frozen=True)
class CodingSubmissionContext:
    """Shared state after a coding task row is prepared for submit.

    Attributes:
        task_row_id: Primary key of the active coding task row.
        task_id: YAML task ID.
        round_num: Follow-up round (0 = initial).
        order: Display order of the task.
        prompt_text: Task prompt for the evaluated round.
        task_spec: Persisted task metadata for the round.
        locale: Section locale for AI feedback.
        initial_prompt_text: Original task prompt for follow-up rounds.
        initial_source_code: Initial submitted code for follow-up rounds.
        submit_test_summary: Hidden test summary captured on submit.
        run_attempts: Serialized Run attempt history for the task row.
    """

    task_row_id: int
    task_id: str
    round_num: int
    order: int
    prompt_text: str
    task_spec: dict[str, Any]
    locale: str
    initial_prompt_text: str
    initial_source_code: str
    submit_test_summary: dict[str, Any]
    run_attempts: tuple[dict[str, Any], ...]


class CodingSubmissionService:
    """Handle coding submit messages and stream server events."""

    def __init__(
        self,
        uow: InterviewUnitOfWork,
        *,
        persistence: CodingEvaluationPersistenceService | None = None,
    ) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this submission workflow.
            persistence: Optional evaluation persistence collaborator.
        """
        self._uow = uow
        navigation = CodingNavigationService(uow)
        self._navigation = navigation
        self._persistence = persistence or CodingEvaluationPersistenceService(
            uow, navigation=navigation
        )

    def _commit_submission_workflow(self) -> None:
        """Commit durable submission changes for the current request scope."""
        self._uow.commit()

    def _rollback_submission_workflow(self) -> None:
        """Discard uncommitted submission changes after a workflow failure."""
        self._uow.rollback()

    def _ensure_interview_active(self, interview_id: str) -> None:
        """Ensure the parent interview session accepts coding actions.

        Args:
            interview_id: Parent interview UUID.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is completed.
        """
        aggregate = self._uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            raise InterviewNotFoundError(interview_id)
        aggregate.ensure_active()

    async def _prepare_submission(
        self,
        *,
        interview_id: str,
        task_id: str,
        source_code: str,
    ) -> CodingSubmissionContext:
        """Run hidden tests and persist the submitted code snapshot.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID for the active coding round.
            source_code: Monaco editor contents at submit time.

        Returns:
            Submission context for AI evaluation.

        Raises:
            CodingSectionNotFoundError: If no coding section exists.
            CodingSectionNotActiveError: If the coding section is not active.
            CodingTaskNotCurrentError: If ``task_id`` is not the active task.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            raise CodingSectionNotFoundError(interview_id)
        section.ensure_active()
        current_task = section.require_current_task(task_id)
        run_attempts = self._serialize_run_attempts(
            self._uow.code_run_attempts.list_for_task(current_task.id)
        )
        round_num = current_task.round
        order = current_task.order
        prompt_text = current_task.prompt_text
        task_spec = dict(current_task.task_spec)
        locale = section.locale
        task_row_id = current_task.id
        initial_prompt_text = current_task.prompt_text
        initial_source_code = source_code
        if current_task.round > 0:
            initial = next(
                task
                for task in section.tasks
                if task.task_id == task_id and task.round == 0
            )
            initial_prompt_text = initial.prompt_text
            initial_source_code = initial.submitted_code or ""

        hidden_result = await CodingRunnerService.run_hidden_tests(
            source_code=source_code,
            task_spec=task_spec,
        )
        submit_test_summary = coding_run_result_to_summary(hidden_result)

        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            raise CodingSectionNotFoundError(interview_id)
        section.ensure_active()
        updated = section.with_submit_test_summary(
            task_row_id,
            submit_test_summary,
            source_code=source_code,
        )
        self._uow.coding_sections.save_aggregate(updated)
        self._uow.flush()

        return CodingSubmissionContext(
            task_row_id=task_row_id,
            task_id=task_id,
            round_num=round_num,
            order=order,
            prompt_text=prompt_text,
            task_spec=task_spec,
            locale=locale,
            initial_prompt_text=initial_prompt_text,
            initial_source_code=initial_source_code,
            submit_test_summary=submit_test_summary,
            run_attempts=run_attempts,
        )

    @staticmethod
    def _serialize_run_attempts(
        attempts: tuple[Any, ...],
    ) -> tuple[dict[str, Any], ...]:
        """Convert domain run attempts into evaluator prompt payloads.

        Args:
            attempts: Persisted domain run attempts.

        Returns:
            Tuple of serialized attempt dicts.
        """
        return tuple(
            {
                "attempt_no": attempt.attempt_no,
                "source_code": attempt.source_code,
                "status": attempt.status,
                "stderr": attempt.stderr,
                "compile_output": attempt.compile_output,
                "tests_passed": attempt.tests_passed,
                "tests_total": attempt.tests_total,
                "test_results": list(attempt.test_results),
            }
            for attempt in attempts
        )

    async def stream_submit(
        self,
        *,
        interview_id: str,
        task_id: str,
        source_code: str,
        provider: AIProvider,
    ) -> AsyncIterator[InterviewEvent | CodingFeedbackEvent]:
        """Persist a coding submission and stream evaluation events.

        Args:
            interview_id: Parent interview UUID.
            task_id: YAML task ID for the active coding round.
            source_code: Monaco editor contents at submit time.
            provider: AI provider for coding evaluation.

        Yields:
            Semantic events mapped to WebSocket payloads by the API layer.

        Raises:
            InterviewNotFoundError: If the interview does not exist.
            InterviewNotActiveError: If the interview is completed.
            CodingSectionNotFoundError: If no coding section exists.
            CodingSectionNotActiveError: If the coding section is not active.
            CodingTaskNotCurrentError: If ``task_id`` is not the active task.
        """
        try:
            async for event in self._iter_submit(
                interview_id=interview_id,
                task_id=task_id,
                source_code=source_code,
                provider=provider,
            ):
                yield event
            self._commit_submission_workflow()
        except Exception:
            self._rollback_submission_workflow()
            raise

    async def stream_timeout_submission(
        self,
        *,
        interview_id: str,
        task_id: str,
        round_num: int,
    ) -> AsyncIterator[CodingFeedbackEvent]:
        """Record an expired coding round with zero score and advance."""
        try:
            yield self._persist_timed_out_round(
                interview_id=interview_id,
                task_id=task_id,
                round_num=round_num,
            )
            self._commit_submission_workflow()
        except Exception:
            self._rollback_submission_workflow()
            raise

    def _persist_timed_out_round(
        self,
        *,
        interview_id: str,
        task_id: str,
        round_num: int,
    ) -> CodingFeedbackEvent:
        self._ensure_interview_active(interview_id)
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            raise CodingSectionNotFoundError(interview_id)
        section.ensure_active()
        limit = section.task_time_limit_seconds
        if not limit:
            raise CodingTaskTimerError("Coding task timer is not enabled")
        current = section.require_current_task(task_id)
        if current.round != round_num:
            raise CodingTaskNotCurrentError(interview_id, task_id)
        if current.submitted_code is not None:
            return CodingFeedbackEvent(
                task_id=task_id,
                order=current.order,
                round=round_num,
                follow_up_needed=False,
                follow_up_text=None,
                follow_up_mode=None,
                next_task=None,
            )
        if not current.client_timeout_due(limit, datetime.now(UTC)):
            raise CodingTaskTimerError("Coding task timer has not expired")
        feedback = timeout_feedback_for_locale(section.locale)
        updated = section.with_timed_out_round(current.id, feedback)
        self._uow.coding_sections.save_aggregate(updated)
        next_task, timer_remaining = self._navigation.advance_to_next_unsubmitted(
            interview_id,
            task_id=task_id,
            round_num=round_num,
        )
        return CodingFeedbackEvent(
            task_id=task_id,
            order=current.order,
            round=round_num,
            follow_up_needed=False,
            follow_up_text=None,
            follow_up_mode=None,
            next_task=next_task,
            feedback=feedback,
            timer_remaining_seconds=timer_remaining,
        )

    async def _iter_submit(
        self,
        *,
        interview_id: str,
        task_id: str,
        source_code: str,
        provider: AIProvider,
    ) -> AsyncIterator[InterviewEvent | CodingFeedbackEvent]:
        self._ensure_interview_active(interview_id)
        ctx = await self._prepare_submission(
            interview_id=interview_id,
            task_id=task_id,
            source_code=source_code,
        )

        yield AnswerSavedEvent()
        yield EvaluatingEvent()

        (
            evaluation,
            follow_up_needed,
            follow_up_text,
            follow_up_mode,
        ) = await asyncio.shield(
            CodingEvaluatorService.evaluate_submission(
                provider=provider,
                locale=ctx.locale,
                answer_round=ctx.round_num,
                prompt_text=ctx.prompt_text,
                task_spec=ctx.task_spec,
                source_code=source_code,
                run_attempts=ctx.run_attempts,
                submit_test_summary=ctx.submit_test_summary,
                initial_prompt_text=ctx.initial_prompt_text,
                initial_source_code=ctx.initial_source_code,
            )
        )

        yield self._persistence.persist(
            interview_id=interview_id,
            task_id=ctx.task_id,
            round_num=ctx.round_num,
            order=ctx.order,
            evaluation=evaluation,
            follow_up_needed=follow_up_needed,
            follow_up_text=follow_up_text,
            follow_up_mode=cast(Literal["code", "explanation"] | None, follow_up_mode),
            submit_test_summary=ctx.submit_test_summary,
            submitted_source_code=source_code,
        )
