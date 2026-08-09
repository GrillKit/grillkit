# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Assemble interview read models from domain aggregates."""

from __future__ import annotations

from app.coding.domain.entities import CodingSection as DomainCodingSection
from app.interview.domain.entities import Interview as DomainInterview
from app.interview.domain.scoring import resolve_completed_read_score
from app.interview.repositories.mappers import compose_interview_read
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.theory.domain.entities import TheorySection as DomainTheorySection


def _assemble_interview_read(
    shell: DomainInterview,
    theory: DomainTheorySection | None,
    coding: DomainCodingSection | None = None,
) -> InterviewRead:
    """Compose an interview read model with a resolved display score.

    Args:
        shell: Interview shell aggregate.
        theory: Theory section aggregate with tasks, if present.
        coding: Coding section aggregate, if present.

    Returns:
        Immutable interview read model for services, API, and templates.
    """
    read_model = compose_interview_read(shell, theory, coding)
    score = resolve_completed_read_score(shell, theory, coding)
    if score is None:
        return read_model
    return read_model.model_copy(update={"score": score})


def assemble_interview_read(
    shell: DomainInterview,
    theory: DomainTheorySection | None,
    coding: DomainCodingSection | None = None,
) -> InterviewRead:
    """Compose an interview read model with a resolved display score.

    Args:
        shell: Interview shell aggregate.
        theory: Theory section aggregate with tasks, if present.
        coding: Coding section aggregate, if present.

    Returns:
        Immutable interview read model for services, API, and templates.
    """
    read_model = compose_interview_read(shell, theory, coding)
    score = resolve_completed_read_score(shell, theory, coding)
    if score is None:
        return read_model
    return read_model.model_copy(update={"score": score})


def load_interview_read(
    uow: InterviewUnitOfWork,
    interview_id: str,
) -> InterviewRead | None:
    """Load a composed interview read model for one session.

    Args:
        uow: Active application unit of work.
        interview_id: Parent session UUID.

    Returns:
        Interview read model, or None when the session does not exist.
    """
    shell = uow.interviews.get_aggregate(interview_id)
    if shell is None:
        return None
    theory = uow.theory_sections.get_aggregate(interview_id)
    coding = uow.coding_sections.get_aggregate(interview_id)
    return assemble_interview_read(shell, theory, coding)


def load_recent_interview_reads(
    uow: InterviewUnitOfWork,
    *,
    limit: int = 20,
) -> list[InterviewRead]:
    """Load recent interview read models, newest first.

    Args:
        uow: Active application unit of work.
        limit: Maximum number of sessions to return.

    Returns:
        Composed interview read models with theory tasks when present.
    """
    shells = uow.interviews.list_recent_aggregates(limit=limit)
    if not shells:
        return []
    interview_ids = [shell.id for shell in shells]
    theory_by_id = uow.theory_sections.get_aggregates_by_interview_ids(interview_ids)
    coding_by_id = uow.coding_sections.get_aggregates_by_interview_ids(interview_ids)
    return [
        assemble_interview_read(
            shell,
            theory_by_id.get(shell.id),
            coding_by_id.get(shell.id),
        )
        for shell in shells
    ]


class InterviewProjection:
    """Build interview read-model projections from domain aggregates."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this read scope.
        """
        self._uow = uow

    def load(self, interview_id: str) -> InterviewRead | None:
        """Load a composed interview read model for one session.

        Args:
            interview_id: Parent session UUID.

        Returns:
            Interview read model, or None when the session does not exist.
        """
        shell = self._uow.interviews.get_aggregate(interview_id)
        if shell is None:
            return None
        theory = self._uow.theory_sections.get_aggregate(interview_id)
        coding = self._uow.coding_sections.get_aggregate(interview_id)
        return _assemble_interview_read(shell, theory, coding)

    def load_recent(self, *, limit: int = 20) -> list[InterviewRead]:
        """Load recent interview read models, newest first.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            Composed interview read models with theory tasks when present.
        """
        shells = self._uow.interviews.list_recent_aggregates(limit=limit)
        if not shells:
            return []
        interview_ids = [shell.id for shell in shells]
        theory_by_id = self._uow.theory_sections.get_aggregates_by_interview_ids(
            interview_ids
        )
        coding_by_id = self._uow.coding_sections.get_aggregates_by_interview_ids(
            interview_ids
        )
        return [
            _assemble_interview_read(
                shell,
                theory_by_id.get(shell.id),
                coding_by_id.get(shell.id),
            )
            for shell in shells
        ]

    @staticmethod
    def assemble(
        shell: DomainInterview,
        theory: DomainTheorySection | None,
        coding: DomainCodingSection | None = None,
    ) -> InterviewRead:
        """Compose an interview read model with a resolved display score.

        Args:
            shell: Interview shell aggregate.
            theory: Theory section aggregate with tasks, if present.
            coding: Coding section aggregate, if present.

        Returns:
            Immutable interview read model for services, API, and templates.
        """
        return _assemble_interview_read(shell, theory, coding)
