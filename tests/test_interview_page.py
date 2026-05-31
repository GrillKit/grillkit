# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview page context building."""

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.page import InterviewPageService
from app.platform.services.config import AppConfig
from tests.helpers.selection import minimal_selection_spec

_SPEC = minimal_selection_spec()


def _session() -> InterviewRead:
    """Build a minimal active interview read model."""
    return InterviewRead(
        id="s1",
        status="active",
        locale="en",
        selection_spec=_SPEC,
        question_ids='["q1"]',
        question_count=1,
        question_time_limit_seconds=None,
        answers=[
            AnswerRead(
                id=1,
                question_id="q1",
                order=1,
                round=0,
                question_text="Question?",
                question_code=None,
                answer_text=None,
                score=None,
                started_at=None,
            )
        ],
    )


def test_build_page_context_sets_audio_flag_from_catalog(monkeypatch):
    """Page context reflects whether the configured LLM accepts audio input."""
    monkeypatch.setattr(
        "app.interview.services.page.LLMCatalogService.get_model",
        lambda preset_id: type(
            "Entry",
            (),
            {"accepts_audio_input": preset_id == "audio-model"},
        )(),
    )

    enabled = InterviewPageService.build_page_context(
        _session(),
        config=AppConfig(
            llm_preset_id="audio-model",
            provider_type="openai-compatible",
            base_url="http://localhost:11434/v1",
            model="test",
            timeout=60,
        ),
        question_voice_enabled=False,
    )
    disabled = InterviewPageService.build_page_context(
        _session(),
        config=AppConfig(
            llm_preset_id="text-model",
            provider_type="openai-compatible",
            base_url="http://localhost:11434/v1",
            model="test",
            timeout=60,
        ),
        question_voice_enabled=False,
    )

    assert enabled.interview_model_accepts_audio is True
    assert disabled.interview_model_accepts_audio is False
