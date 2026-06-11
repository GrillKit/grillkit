# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Session phase transitions between interview sections."""

from app.interview.domain.serialization import parse_session_spec
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.sections import (
    SectionKind,
    phase_order_for_mode,
    section_services,
)


class SessionPhaseOrchestrator:
    """Coordinate phase completion hooks across interview sections."""

    @staticmethod
    def active_phase(interview_id: str) -> SectionKind | None:
        """Return the section kind the user should interact with now.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Active section kind, or None when the session row is missing.
        """
        with InterviewUnitOfWork() as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                return None
            order = phase_order_for_mode(aggregate.selection.session_mode)

        services = section_services()
        for kind in order:
            services[kind].activate_if_pending(interview_id)
            if services[kind].is_user_facing(interview_id):
                return kind
            if not services[kind].is_complete(interview_id):
                return kind
        return order[-1] if order else None

    @staticmethod
    def notify_section_complete(interview_id: str, section_kind: SectionKind) -> None:
        """Invoke section prefetch hooks when a phase finishes.

        Args:
            interview_id: Parent interview UUID.
            section_kind: Section that the user just completed.
        """
        services = section_services()
        services[section_kind].on_phase_complete(interview_id)
        services["coding"].activate_if_pending(interview_id)

    @staticmethod
    def session_mode_for_interview(interview_id: str) -> str:
        """Load the session mode for an interview row.

        Args:
            interview_id: Parent interview UUID.

        Returns:
            Session mode string, defaulting to ``theory_only`` when missing.
        """
        with InterviewUnitOfWork() as uow:
            row = uow.interviews.get(interview_id)
            if row is None:
                return "theory_only"
            return parse_session_spec(row.selection_spec).session_mode
