# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding task submit orchestration for the coding WebSocket."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, cast

from app.ai.base import AIProvider
from app.coding.domain.exceptions import CodingSectionNotFoundError
from app.coding.repositories.uow import CodingUnitOfWork
from app.coding.services.evaluation_persistence import (
    CodingEvaluationPersistenceService,
)
from app.coding.services.evaluator.service import CodingEvaluatorService
from app.coding.services.events import CodingFeedbackEvent
from app.coding.services.run_execution import (
    _ensure_interview_active,
    coding_run_result_to_summary,
)
from app.coding.services.runner import CodingRunnerService
from app.interview.services.events import (
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewEvent,
)


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

    @staticmethod
    async def _prepare_submission(
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
        with CodingUnitOfWork() as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                raise CodingSectionNotFoundError(interview_id)
            section.ensure_active()
            current_task = section.require_current_task(task_id)
            run_attempts = CodingSubmissionService._serialize_run_attempts(
                uow.code_run_attempts.list_for_task(current_task.id)
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

        with CodingUnitOfWork(auto_commit=True) as uow:
            section = uow.coding_sections.get_aggregate(interview_id)
            if section is None:
                raise CodingSectionNotFoundError(interview_id)
            section.ensure_active()
            updated = section.with_submit_test_summary(
                task_row_id,
                submit_test_summary,
                source_code=source_code,
            )
            uow.coding_sections.save_aggregate(updated)

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

    @staticmethod
    async def stream_submit(
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
        _ensure_interview_active(interview_id)
        ctx = await CodingSubmissionService._prepare_submission(
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

        yield CodingEvaluationPersistenceService.persist(
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
