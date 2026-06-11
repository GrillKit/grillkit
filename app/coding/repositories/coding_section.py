# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section repository."""

import json

from sqlalchemy.orm import Session, selectinload

from app.coding.domain.entities import CodingSection as DomainCodingSection
from app.coding.domain.entities import CodingTask as DomainCodingTask
from app.coding.domain.exceptions import CodingSectionNotFoundError
from app.coding.repositories.mappers import (
    coding_section_from_orm,
    coding_section_to_orm,
    coding_section_to_orm_fields,
    domain_coding_task_to_orm,
)
from app.shared.infrastructure.models import CodingSection
from app.shared.repositories.base import SqlAlchemyRepository


class CodingSectionRepository(SqlAlchemyRepository[CodingSection]):
    """Repository for ``CodingSection`` entities.

    Attributes:
        _session: Active SQLAlchemy Session (inherited).
    """

    _model = CodingSection

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        super().__init__(session)

    def get_by_interview_id(self, interview_id: str) -> CodingSection | None:
        """Retrieve a coding section by parent interview ID.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            CodingSection ORM row with tasks loaded, or None.
        """
        return (
            self._session.query(CodingSection)
            .options(selectinload(CodingSection.tasks))
            .filter_by(interview_id=interview_id)
            .first()
        )

    def get_aggregate(self, interview_id: str) -> DomainCodingSection | None:
        """Load a domain coding section aggregate with tasks.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Domain aggregate, or None when the section does not exist.
        """
        orm_section = self.get_by_interview_id(interview_id)
        if orm_section is None:
            return None
        return coding_section_from_orm(orm_section)

    def create_aggregate(self, section: DomainCodingSection) -> DomainCodingSection:
        """Insert a coding section and its task rows.

        Args:
            section: Domain section with tasks to persist.

        Returns:
            Reloaded domain aggregate with assigned IDs.

        Raises:
            CodingSectionNotFoundError: If reload fails after flush.
        """
        orm_section = coding_section_to_orm(section)
        self._session.add(orm_section)
        self._session.flush()
        for task in section.tasks:
            self._session.add(
                domain_coding_task_to_orm(task, coding_section_id=orm_section.id)
            )
        self._session.flush()
        reloaded = self.get_by_interview_id(section.interview_id)
        if reloaded is None:
            raise CodingSectionNotFoundError(section.interview_id)
        return coding_section_from_orm(reloaded)

    def save_aggregate(self, section: DomainCodingSection) -> None:
        """Persist mutable section and task fields from a domain aggregate.

        Args:
            section: Domain section previously loaded from this repository.

        Raises:
            CodingSectionNotFoundError: If the section row no longer exists.
        """
        orm_section = self.get_by_interview_id(section.interview_id)
        if orm_section is None:
            raise CodingSectionNotFoundError(section.interview_id)

        for field, value in coding_section_to_orm_fields(section).items():
            setattr(orm_section, field, value)

        orm_tasks_by_id = {task.id: task for task in orm_section.tasks}
        for domain_task in section.tasks:
            if domain_task.id == DomainCodingTask.NEW_ID:
                orm_section.tasks.append(
                    domain_coding_task_to_orm(
                        domain_task, coding_section_id=orm_section.id
                    )
                )
                continue
            orm_task = orm_tasks_by_id.get(domain_task.id)
            if orm_task is None:
                continue
            orm_task.submitted_code = domain_task.submitted_code
            orm_task.submit_test_summary = (
                json.dumps(domain_task.submit_test_summary, separators=(",", ":"))
                if domain_task.submit_test_summary is not None
                else None
            )
            orm_task.score = domain_task.score
            orm_task.feedback = domain_task.feedback
            orm_task.started_at = domain_task.started_at
