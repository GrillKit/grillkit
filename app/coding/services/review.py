# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section review page context builder."""

from __future__ import annotations

from app.coding.domain.entities import CodingSection
from app.coding.schemas.review import (
    CodingReviewContext,
    CodingTaskReviewRead,
    CodingTaskRoundRead,
)
from app.coding.services.query import CodingQueryService
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.section_review_support import (
    CompletedInterviewSnapshot,
    load_completed_interview,
    resolved_section_feedback,
    review_score_fields,
    shared_review_fields,
)


class CodingReviewService:
    """Build read-only coding review context for completed sessions."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this review scope.
        """
        self._uow = uow
        self._query = CodingQueryService(uow)

    @staticmethod
    def _group_tasks(section: CodingSection) -> list[CodingTaskReviewRead]:
        """Group submitted coding task rows by display order.

        Args:
            section: Coding section aggregate with tasks loaded.

        Returns:
            Task review rows sorted by display order.
        """
        submitted = [task for task in section.tasks if task.submitted_code is not None]
        orders = sorted({task.order for task in submitted})
        grouped: list[CodingTaskReviewRead] = []

        for order in orders:
            rounds = sorted(
                (task for task in submitted if task.order == order),
                key=lambda task: task.round,
            )
            if not rounds:
                continue
            initial = next(
                (task for task in rounds if task.round == 0),
                rounds[0],
            )
            round_reads = [
                CodingTaskRoundRead(
                    round=task.round,
                    prompt_text=task.prompt_text,
                    submitted_code=task.submitted_code or "",
                    score=task.score,
                    feedback=task.feedback,
                    submit_test_summary=(
                        task.submit_test_summary if task.round == 0 else None
                    ),
                )
                for task in rounds
            ]
            total_score = sum(
                task.score for task in rounds if isinstance(task.score, int)
            )
            max_score = len(rounds) * CodingSection.MAX_SCORE_PER_ROUND
            grouped.append(
                CodingTaskReviewRead(
                    order=order,
                    task_id=initial.task_id,
                    initial_prompt=initial.prompt_text,
                    total_score=total_score,
                    max_score=max_score,
                    rounds=round_reads,
                )
            )

        return grouped

    def build_context(
        self,
        interview_id: str,
        snapshot: CompletedInterviewSnapshot,
    ) -> CodingReviewContext | None:
        """Assemble coding review template context for a completed session.

        Args:
            interview_id: Parent session UUID.
            snapshot: Loaded completed interview snapshot.

        Returns:
            Review context, or None when the coding section is missing.
        """
        section = self._uow.coding_sections.get_aggregate(interview_id)
        if section is None:
            return None

        summary = self._query.get_evaluation_summary(interview_id)
        if summary is None:
            return None

        section_feedback = resolved_section_feedback(
            summary,
            item_id_key="task_id",
            cached_payload=section.section_feedback,
        )
        scores = review_score_fields(
            summary,
            total_score=section.total_score(),
            max_score=section.max_score(),
        )

        return CodingReviewContext(
            **{
                **shared_review_fields(interview_id, snapshot),
                **scores,
                "section_feedback": section_feedback,
                "tasks": self._group_tasks(section),
            }
        )

    def build_context_for(self, interview_id: str) -> CodingReviewContext | None:
        """Build coding review context for a completed session.

        Args:
            interview_id: Parent session UUID.

        Returns:
            Review context, or None when the session or coding section is missing.
        """
        snapshot = load_completed_interview(self._uow, interview_id)
        if snapshot is None:
            return None
        return self.build_context(interview_id, snapshot)
