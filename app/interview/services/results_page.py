# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Completed session results hub page context builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.interview.domain.serialization import parse_session_spec
from app.interview.domain.value_objects import SectionKind, session_mode_label
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewRead
from app.interview.schemas.results import SectionResultCard, SessionResultsContext
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.read_model import load_interview_read
from app.interview.services.rules.selection import session_selection_summary_lines
from app.interview.services.section_review_support import (
    item_id_key_for,
    resolved_section_feedback,
)
from app.interview.services.sections import (
    SectionEvaluationSummary,
    phase_order_for_mode,
    section_services,
)
from app.shared.locales import SUPPORTED_LOCALES

_SECTION_LABELS: dict[SectionKind, str] = {
    "theory": "Theory",
    "coding": "Coding",
}


@dataclass(frozen=True)
class SessionResultsRender:
    """Result of preparing a session results HTML page.

    Attributes:
        redirect_url: Redirect target when the session is missing or not completed.
        template_context: Jinja context when the page should render.
    """

    redirect_url: str | None
    template_context: dict[str, Any] | None


class SessionResultsPageService:
    """Compose the completed session results hub template context."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this page scope.
        """
        self._uow = uow

    @staticmethod
    def _section_summary_text(
        section_key: SectionKind,
        summary: SectionEvaluationSummary,
    ) -> str:
        """Build a short excerpt for a section results card.

        Args:
            section_key: Section kind identifier.
            summary: Section evaluation summary.

        Returns:
            Short summary text for display on the results hub.
        """
        feedback = resolved_section_feedback(
            summary,
            item_id_key=item_id_key_for(section_key),
            cached_payload=summary.cached_narrative,
        )
        narrative = str(feedback.get("section_feedback", "")).strip()
        if narrative:
            return narrative
        return f"{section_key.capitalize()} section complete."

    @staticmethod
    def _section_card(
        interview_id: str,
        kind: SectionKind,
        summary: SectionEvaluationSummary,
        breakdown: dict[str, Any] | None,
    ) -> SectionResultCard:
        """Build one section result card from summary and session breakdown.

        Args:
            interview_id: Parent session UUID.
            kind: Section kind identifier.
            summary: Section evaluation summary.
            breakdown: Nested session score breakdown, if present.

        Returns:
            Section result card for the results hub template.
        """
        section_data = breakdown.get(kind) if isinstance(breakdown, dict) else None
        score = (
            int(section_data.get("score", 0))
            if isinstance(section_data, dict)
            else summary.score
        )
        section_max = (
            int(section_data.get("max", 0))
            if isinstance(section_data, dict)
            else summary.max_score
        )
        skipped = (
            bool(section_data.get("skipped"))
            if isinstance(section_data, dict)
            else summary.skipped
        )
        return SectionResultCard(
            section=kind,
            label=_SECTION_LABELS[kind],
            score=score,
            max_score=section_max,
            skipped=skipped,
            summary=SessionResultsPageService._section_summary_text(kind, summary),
            detail_url=f"/interview/{interview_id}/{kind}",
        )

    def build_context(self, interview: InterviewRead) -> SessionResultsContext | None:
        """Assemble results hub context for a completed session.

        Args:
            interview: Completed interview read model.

        Returns:
            Results context, or None when overall feedback is missing.
        """
        if interview.status != "completed" or interview.overall_feedback is None:
            return None

        session = parse_session_spec(interview.selection_spec)
        breakdown = interview.overall_feedback.get("score_breakdown")
        max_score = DashboardBuilder.compute_max_score(
            interview,
            breakdown if isinstance(breakdown, dict) else None,
            uow=self._uow,
        )

        services = section_services(self._uow)
        section_cards: list[SectionResultCard] = []
        theory_review_url: str | None = None
        coding_review_url: str | None = None

        for kind in phase_order_for_mode(session.session_mode):
            summary = services[kind].get_evaluation_summary(interview.id)
            if summary is None:
                continue
            card = self._section_card(
                interview.id,
                kind,
                summary,
                breakdown if isinstance(breakdown, dict) else None,
            )
            section_cards.append(card)
            if kind == "theory":
                theory_review_url = card.detail_url
            elif kind == "coding":
                coding_review_url = card.detail_url

        return SessionResultsContext(
            interview=interview,
            interview_title=DashboardBuilder.interview_display_title(interview),
            selection_lines=session_selection_summary_lines(session),
            session_mode_label=session_mode_label(session.session_mode),
            locale_label=SUPPORTED_LOCALES.get(interview.locale, interview.locale),
            max_score=max_score,
            overall_feedback=interview.overall_feedback,
            section_cards=section_cards,
            theory_review_url=theory_review_url,
            coding_review_url=coding_review_url,
        )

    def prepare_page(self, interview_id: str) -> SessionResultsRender:
        """Load a completed session and build the results hub context.

        Args:
            interview_id: Session UUID.

        Returns:
            Redirect URL or template context for ``session_results.html``.
        """
        interview = load_interview_read(self._uow, interview_id)

        if interview is None:
            return SessionResultsRender(redirect_url="/", template_context=None)
        if interview.status != "completed":
            return SessionResultsRender(
                redirect_url=f"/interview/{interview_id}",
                template_context=None,
            )

        context = self.build_context(interview)
        if context is None:
            return SessionResultsRender(
                redirect_url=f"/interview/{interview_id}",
                template_context=None,
            )

        return SessionResultsRender(
            redirect_url=None,
            template_context=context.model_dump(),
        )
