# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview session page context builder."""

from dataclasses import dataclass
from typing import Any

from app.coding.services.page import CodingPageService
from app.interview.domain.serialization import parse_session_spec
from app.interview.domain.value_objects import SESSION_MODE_LABELS
from app.interview.schemas.interview import InterviewPageContext, InterviewRead
from app.interview.services.dashboard import DashboardBuilder
from app.interview.services.phases import SessionPhaseOrchestrator
from app.interview.services.query import InterviewQuery
from app.interview.services.rules.selection import (
    session_display_title,
    session_selection_summary_lines,
)
from app.interview.services.sections import phase_order_for_mode
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
from app.theory.services.page import TheoryPageService


@dataclass(frozen=True)
class SessionPageRender:
    """Result of preparing the interview HTML page.

    Attributes:
        redirect_url: Redirect target when the session is missing.
        template_context: Jinja context when the page should render.
        interview_active: Whether the loaded session is still active.
    """

    redirect_url: str | None
    template_context: dict[str, Any] | None
    interview_active: bool = False


class SessionPageService:
    """Compose session shell and section contexts for the interview page."""

    @staticmethod
    def load_interview(interview_id: str) -> InterviewRead | None:
        """Load a session and start the active phase timer when enabled.

        Args:
            interview_id: The session UUID.

        Returns:
            Interview read model, or None when not found.
        """
        active_phase = SessionPhaseOrchestrator.active_phase(interview_id)
        if active_phase == "theory":
            TheoryPageService.activate_timer(interview_id)
        elif active_phase == "coding":
            CodingPageService.activate_timer(interview_id)
        return InterviewQuery.get_interview(interview_id)

    @staticmethod
    async def prepare_page(
        interview_id: str,
        *,
        config: AppConfig | None,
        whisper_model_service: type[WhisperModelService] = WhisperModelService,
    ) -> SessionPageRender:
        """Load a session and build template context for the interview page.

        Args:
            interview_id: The session UUID.
            config: Saved provider configuration, if any.
            whisper_model_service: Whisper model service class (injectable in tests).

        Returns:
            Redirect URL or template context for ``interview.html``.
        """
        interview = SessionPageService.load_interview(interview_id)
        if interview is None:
            return SessionPageRender(redirect_url="/", template_context=None)

        template_context = await SessionPageService.build_full_template_context(
            interview,
            config=config,
            whisper_model_service=whisper_model_service,
        )
        return SessionPageRender(
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
        """Assemble shell template context for ``interview.html``.

        Theory-specific fields are merged from ``TheoryPageService`` for template
        compatibility while ``theory`` exposes the structured section context.

        Args:
            interview: Loaded interview read model.
            config: Application config, if configured.
            question_voice_enabled: Whether Piper TTS is enabled in config.

        Returns:
            Frozen page context for the interview template.
        """
        theory = TheoryPageService.build_context(interview)
        current_question = theory.current_question if theory is not None else None
        question_timer_enabled = (
            theory.question_timer_enabled if theory is not None else False
        )
        timer_remaining_seconds = (
            theory.timer_remaining_seconds if theory is not None else None
        )
        current_round = theory.current_round if theory is not None else 0
        answers = theory.answers if theory is not None else interview.answers

        overall_feedback_data = interview.overall_feedback
        score_breakdown = (
            overall_feedback_data.get("score_breakdown")
            if overall_feedback_data
            else None
        )
        max_score = DashboardBuilder.compute_max_score(
            interview,
            score_breakdown if isinstance(score_breakdown, dict) else None,
        )
        session = parse_session_spec(
            interview.selection_spec,
            question_count=interview.question_count,
            task_time_limit_seconds=interview.question_time_limit_seconds,
        )
        selection_lines = session_selection_summary_lines(session)
        interview_title = session_display_title(session)
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
            answers=answers,
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
        """Merge session shell, theory section, and audio keys for ``interview.html``.

        Args:
            interview: Loaded interview read model.
            config: Application config, if configured.
            whisper_model_service: Whisper model service class (injectable in tests).

        Returns:
            Flat dict for Jinja template rendering.
        """
        session = parse_session_spec(
            interview.selection_spec,
            question_count=interview.question_count,
            task_time_limit_seconds=interview.question_time_limit_seconds,
        )
        theory = TheoryPageService.build_context(interview)
        coding = CodingPageService.build_context(interview.id)
        base = SessionPageService.build_page_context(
            interview,
            config=config,
            question_voice_enabled=bool(config and config.question_voice_enabled),
        ).model_dump()
        speech = SpeechModelPageService.build_page_context(
            config,
            whisper_model_service=whisper_model_service,
        ).model_dump()
        voice = (await QuestionVoicePageService.build_page_context(config)).model_dump()
        return {
            **base,
            **speech,
            **voice,
            "theory": theory.model_dump() if theory is not None else None,
            "coding": coding.model_dump() if coding is not None else None,
            "session_mode": session.session_mode,
            "session_mode_label": SESSION_MODE_LABELS.get(
                session.session_mode, session.session_mode
            ),
            "phase_order": list(phase_order_for_mode(session.session_mode)),
            "active_phase": SessionPhaseOrchestrator.active_phase(interview.id),
        }
