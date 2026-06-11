# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory section repository.

Provides data access for ``TheorySection`` records keyed by interview ID.
"""

from sqlalchemy.orm import Session, selectinload

from app.shared.infrastructure.models import TheorySection
from app.shared.repositories.base import SqlAlchemyRepository
from app.theory.domain.entities import TheorySection as DomainTheorySection
from app.theory.domain.entities import TheoryTask as DomainTheoryTask
from app.theory.domain.exceptions import TheorySectionNotFoundError
from app.theory.repositories.mappers import (
    domain_theory_task_to_orm,
    theory_section_from_orm,
    theory_section_to_orm,
    theory_section_to_orm_fields,
)


class TheorySectionRepository(SqlAlchemyRepository[TheorySection]):
    """Repository for ``TheorySection`` entities.

    Attributes:
        _session: Active SQLAlchemy Session (inherited).
    """

    _model = TheorySection

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: Active SQLAlchemy Session.
        """
        super().__init__(session)

    def get_by_interview_id(self, interview_id: str) -> TheorySection | None:
        """Retrieve a theory section by parent interview ID.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            TheorySection ORM row with tasks loaded, or None.
        """
        return (
            self._session.query(TheorySection)
            .options(selectinload(TheorySection.tasks))
            .filter_by(interview_id=interview_id)
            .first()
        )

    def get_aggregate(self, interview_id: str) -> DomainTheorySection | None:
        """Load a domain theory section aggregate with tasks.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Domain aggregate, or None when the section does not exist.
        """
        orm_section = self.get_by_interview_id(interview_id)
        if orm_section is None:
            return None
        return theory_section_from_orm(orm_section)

    def create_section(self, section: DomainTheorySection) -> DomainTheorySection:
        """Insert a new theory section row without tasks.

        Args:
            section: Domain section from ``TheorySection.start``.

        Returns:
            Reloaded domain aggregate with assigned section ID.

        Raises:
            TheorySectionNotFoundError: If reload fails after flush.
        """
        orm_section = theory_section_to_orm(section)
        self._session.add(orm_section)
        self._session.flush()
        reloaded = self.get_by_interview_id(section.interview_id)
        if reloaded is None:
            raise TheorySectionNotFoundError(section.interview_id)
        return theory_section_from_orm(reloaded)

    def create_aggregate(self, section: DomainTheorySection) -> DomainTheorySection:
        """Insert a theory section and its task rows.

        Args:
            section: Domain section with tasks to persist.

        Returns:
            Reloaded domain aggregate with assigned IDs.

        Raises:
            TheorySectionNotFoundError: If reload fails after flush.
        """
        orm_section = theory_section_to_orm(section)
        self._session.add(orm_section)
        self._session.flush()
        for task in section.tasks:
            self._session.add(
                domain_theory_task_to_orm(task, theory_section_id=orm_section.id)
            )
        self._session.flush()
        reloaded = self.get_by_interview_id(section.interview_id)
        if reloaded is None:
            raise TheorySectionNotFoundError(section.interview_id)
        return theory_section_from_orm(reloaded)

    def save_section(self, section: DomainTheorySection) -> None:
        """Persist mutable fields from a domain section onto the ORM row.

        Args:
            section: Domain section previously loaded from this repository.

        Raises:
            TheorySectionNotFoundError: If the section row no longer exists.
        """
        orm_section = self.get_by_interview_id(section.interview_id)
        if orm_section is None:
            raise TheorySectionNotFoundError(section.interview_id)

        for field, value in theory_section_to_orm_fields(section).items():
            setattr(orm_section, field, value)

    def save_aggregate(self, section: DomainTheorySection) -> None:
        """Persist mutable section and task fields from a domain aggregate.

        Args:
            section: Domain section previously loaded from this repository.

        Raises:
            TheorySectionNotFoundError: If the section row no longer exists.
        """
        orm_section = self.get_by_interview_id(section.interview_id)
        if orm_section is None:
            raise TheorySectionNotFoundError(section.interview_id)

        for field, value in theory_section_to_orm_fields(section).items():
            setattr(orm_section, field, value)

        orm_tasks_by_id = {task.id: task for task in orm_section.tasks}
        for domain_task in section.tasks:
            if domain_task.id == DomainTheoryTask.NEW_ID:
                orm_section.tasks.append(
                    domain_theory_task_to_orm(
                        domain_task, theory_section_id=orm_section.id
                    )
                )
                continue
            orm_task = orm_tasks_by_id.get(domain_task.id)
            if orm_task is None:
                continue
            orm_task.answer_text = domain_task.answer_text
            orm_task.score = domain_task.score
            orm_task.feedback = domain_task.feedback
            orm_task.started_at = domain_task.started_at
