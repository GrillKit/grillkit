# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session page context builder."""

from dataclasses import dataclass
from typing import Any

from app.interview.repositories.mappers import interview_to_read
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.schemas.interview import InterviewPageContext, InterviewRead
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.selection import get_interview_selection
from app.platform.services.config import AppConfig
from app.platform.services.llm_catalog import LLMCatalogService
from app.question_voice.services.page import QuestionVoicePageService
from app.shared.locales import (
    SUPPORTED_LOCALES,
    TIMEOUT_CHAT_LABELS,
    localized_string,
)
from app.speech.services.page import SpeechModelPageService
from app.speech.services.whisper_model import WhisperModelService


@dataclass(frozen=True)
class InterviewPageRender:
    """Result of preparing the interview HTML page.

    Attributes:
        redirect_url: Redirect target when the session is missing.
        template_context: Jinja context when the page should render.
        interview_active: Whether the loaded session is still active.
    """

    redirect_url: str | None
    template_context: dict[str, Any] | None
    interview_active: bool = False


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
        with InterviewUnitOfWork(auto_commit=True) as uow:
            aggregate = uow.interviews.get_aggregate(interview_id)
            if aggregate is None:
                return None
            if aggregate.status == "active" and aggregate.question_time_limit_seconds:
                current = aggregate.find_first_unanswered()
                if current is not None and current.started_at is None:
                    aggregate = aggregate.start_timer_for_answer(current.id)
                    uow.interviews.save_aggregate(aggregate)
            return interview_to_read(aggregate)

    @staticmethod
    async def prepare_page(
        interview_id: str,
        *,
        config: AppConfig | None,
        whisper_model_service: type[WhisperModelService] = WhisperModelService,
    ) -> InterviewPageRender:
        """Load a session and build template context for the interview page.

        Args:
            interview_id: The session UUID.
            config: Saved provider configuration, if any.
            whisper_model_service: Whisper model service class (injectable in tests).

        Returns:
            Redirect URL or template context for ``interview.html``.
        """
        interview = InterviewPageService.load_interview(interview_id)
        if interview is None:
            return InterviewPageRender(redirect_url="/", template_context=None)

        template_context = await InterviewPageService.build_full_template_context(
            interview,
            config=config,
            whisper_model_service=whisper_model_service,
        )
        return InterviewPageRender(
            redirect_url=None,
            template_context=template_context,
            interview_active=interview.status == "active",
        )

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
            InterviewQuery.timer_remaining_seconds(interview.id)
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

    @staticmethod
    async def build_full_template_context(
        interview: InterviewRead,
        *,
        config: AppConfig | None,
        whisper_model_service: type[WhisperModelService] = WhisperModelService,
    ) -> dict[str, Any]:
        """Merge interview, speech, and question-voice keys for ``interview.html``.

        Args:
            interview: Loaded interview read model.
            config: Application config, if configured.
            whisper_model_service: Whisper model service class (injectable in tests).

        Returns:
            Flat dict for Jinja template rendering.
        """
        base = InterviewPageService.build_page_context(
            interview,
            config=config,
            question_voice_enabled=bool(config and config.question_voice_enabled),
        ).model_dump()
        speech = SpeechModelPageService.build_page_context(
            config,
            whisper_model_service=whisper_model_service,
        ).model_dump()
        voice = (await QuestionVoicePageService.build_page_context(config)).model_dump()
        return {**base, **speech, **voice}
