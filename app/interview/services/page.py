# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session page context builder."""

from app.interview.schemas.interview import InterviewPageContext, InterviewRead
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.selection import get_interview_selection
from app.platform.services.config import AppConfig
from app.platform.services.llm_catalog import LLMCatalogService
from app.shared.locales import (
    SUPPORTED_LOCALES,
    TIMEOUT_CHAT_LABELS,
    localized_string,
)


class InterviewPageService:
    """Build read models and template context for the interview page."""

    @staticmethod
    def load_interview(interview_id: str) -> InterviewRead | None:
        """Load a session and start the timer on the current round when active.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model, or None when not found.
        """
        interview = InterviewQuery.get_interview(interview_id)
        if interview is None:
            return None
        if interview.status == "active":
            InterviewQuery.ensure_current_round_started(interview_id)
            interview = InterviewQuery.get_interview(interview_id)
        return interview

    @staticmethod
    def build_page_context(
        interview: InterviewRead,
        *,
        config: AppConfig | None,
        question_voice_enabled: bool,
    ) -> InterviewPageContext:
        """Assemble template context for ``interview.html``.

        Args:
            interview: Loaded interview read model.
            config: Application config, if configured.
            question_voice_enabled: Whether Piper TTS is enabled.

        Returns:
            Frozen page context for the interview template.
        """
        current_question = InterviewQuery.get_current_unanswered(interview)
        question_timer_enabled = interview.question_time_limit_seconds is not None
        timer_remaining_seconds = (
            InterviewQuery.timer_remaining_for_interview(interview)
            if question_timer_enabled
            else None
        )
        current_round = current_question.round if current_question else 0
        overall_feedback_data = interview.overall_feedback
        max_score = DashboardBuilder.compute_max_score(interview)
        selection = get_interview_selection(interview)
        selection_lines = DashboardBuilder.selection_summary_lines(selection)
        interview_title = DashboardBuilder.interview_display_title(interview)
        interview_model_accepts_audio = False
        if config is not None and config.llm_preset_id:
            entry = LLMCatalogService.get_model(config.llm_preset_id)
            interview_model_accepts_audio = (
                entry is not None and entry.accepts_audio_input
            )

        return InterviewPageContext(
            interview=interview,
            interview_title=interview_title,
            selection_lines=selection_lines,
            answers=interview.answers,
            current_question=current_question,
            current_answer_id=current_question.id if current_question else None,
            question_voice_enabled=question_voice_enabled,
            overall_feedback=overall_feedback_data,
            max_score=max_score,
            locale_label=SUPPORTED_LOCALES.get(interview.locale, interview.locale),
            question_timer_enabled=question_timer_enabled,
            question_time_limit_seconds=interview.question_time_limit_seconds,
            timer_remaining_seconds=timer_remaining_seconds,
            current_round=current_round,
            timeout_chat_label=localized_string(interview.locale, TIMEOUT_CHAT_LABELS),
            llm_request_timeout_seconds=int(config.timeout) if config else 60,
            interview_model_accepts_audio=interview_model_accepts_audio,
        )
