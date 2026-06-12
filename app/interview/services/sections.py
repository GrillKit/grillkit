# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview section registry and shared section value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Protocol, cast

from app.interview.domain.value_objects import SessionMode

SectionKind = Literal["theory", "coding"]


@dataclass(frozen=True, slots=True)
class SectionEvaluationSummary:
    """Evaluation snapshot for one interview section.

    Attributes:
        section: Section kind (``theory`` or ``coding``).
        score: Earned points for the section.
        max_score: Maximum achievable points for the section.
        items: Per-task Q&A rows used for evaluation prompts.
        cached_narrative: Prefetched section feedback payload, if any.
        skipped: True when the user ended the session before completing the section.
    """

    section: SectionKind
    score: int
    max_score: int
    items: tuple[dict[str, Any], ...]
    cached_narrative: dict[str, Any] | None = None
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class SectionPageContext:
    """Minimal page context exposed by an interview section.

    Attributes:
        section: Section kind identifier.
        active: Whether this section is the current user-facing phase.
        complete: Whether the user finished all tasks in this section.
    """

    section: SectionKind
    active: bool
    complete: bool


class SectionService(Protocol):
    """Contract implemented by theory and coding section services."""

    section_kind: ClassVar[SectionKind]

    @staticmethod
    def is_complete(interview_id: str) -> bool:
        """Return whether the section has no remaining user tasks."""

    @staticmethod
    def is_user_facing(interview_id: str) -> bool:
        """Return whether the user should interact with this section now."""

    @staticmethod
    def activate_if_pending(interview_id: str) -> bool:
        """Promote a pending section to active when prerequisites are met."""

    @staticmethod
    def get_page_context(interview_id: str) -> SectionPageContext | None:
        """Return section page metadata for session composition."""

    @staticmethod
    def get_evaluation_summary(
        interview_id: str,
    ) -> SectionEvaluationSummary | None:
        """Return section evaluation data for session completion."""

    @staticmethod
    def on_phase_complete(interview_id: str) -> None:
        """Schedule background prefetch when a phase finishes."""

    @staticmethod
    async def ensure_section_feedback(interview_id: str) -> None:
        """Synchronously prefetch section feedback before session completion."""


def phase_order_for_mode(session_mode: SessionMode) -> tuple[SectionKind, ...]:
    """Return ordered section kinds for a session mode.

    Args:
        session_mode: Session mode from setup.

    Returns:
        Tuple of section kinds in user-facing order.
    """
    if session_mode == "theory_only":
        return ("theory",)
    if session_mode == "coding_only":
        return ("coding",)
    if session_mode == "theory_then_coding":
        return ("theory", "coding")
    return ("coding", "theory")


def is_first_user_facing_section(
    session_mode: SessionMode, section: SectionKind
) -> bool:
    """Return whether ``section`` is the first interactive phase for a session mode.

    Args:
        session_mode: Session mode from setup.
        section: Section kind to check.

    Returns:
        True when ``section`` is the first entry in the mode phase order.
    """
    order = phase_order_for_mode(session_mode)
    return bool(order) and order[0] == section


def section_services() -> dict[SectionKind, SectionService]:
    """Return section service classes keyed by section kind.

    Returns:
        Mapping from section kind to the corresponding section service class.
    """
    from app.coding.services.section import CodingSectionService
    from app.theory.services.section import TheorySectionService

    return cast(
        dict[SectionKind, SectionService],
        {
            "theory": TheorySectionService,
            "coding": CodingSectionService,
        },
    )


def prior_sections_complete_for(interview_id: str, section: SectionKind) -> bool:
    """Return whether every section before ``section`` in phase order is complete.

    Args:
        interview_id: Parent interview UUID.
        section: Target section kind to check prerequisites for.

    Returns:
        True when all prior sections are finished or absent from the phase order.
    """
    from app.interview.repositories.uow import InterviewUnitOfWork

    services = section_services()
    with InterviewUnitOfWork() as uow:
        aggregate = uow.interviews.get_aggregate(interview_id)
        if aggregate is None:
            return False
        order = phase_order_for_mode(aggregate.session_mode)
    if section not in order:
        return False
    target_index = order.index(section)
    for kind in order[:target_index]:
        if not services[kind].is_complete(interview_id):
            return False
    return True
