# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session phase transitions between interview sections."""

from app.interview.domain.value_objects import SectionKind
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.sections import (
    phase_order_for_mode,
    section_services,
)


class SessionPhaseOrchestrator:
    """Coordinate phase completion hooks across interview sections."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this phase scope.
        """
        self._uow = uow

    def active_phase(self, interview_id: str) -> SectionKind | None:
        """Return the section kind the user should interact with now.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Active section kind, or None when the session row is missing.
        """
        aggregate = self._uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            return None
        order = phase_order_for_mode(aggregate.session_mode)

        services = section_services(self._uow)
        for kind in order:
            services[kind].activate_if_pending(interview_id)
            if services[kind].is_user_facing(interview_id):
                return kind
            if not services[kind].is_complete(interview_id):
                return kind
        return order[-1] if order else None

    def notify_section_complete(
        self,
        interview_id: str,
        section_kind: SectionKind,
    ) -> None:
        """Invoke section prefetch hooks when a phase finishes.

        Runs on the orchestrator's unit of work so phase transitions do not open
        a second SQLite connection while the caller still holds a write lock.

        Args:
            interview_id: Parent interview UUID.
            section_kind: Section that the user just completed.
        """
        services = section_services(self._uow)
        services[section_kind].on_phase_complete(interview_id)
        services["coding"].activate_if_pending(interview_id)
