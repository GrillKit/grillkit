# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-audio orchestration for interview sessions."""

from pathlib import Path

from app.interview.api.access import get_current_unanswered, load_interview_or_raise
from app.interview.domain.progress import require_active
from app.interview.domain.interview import interview_view
from app.platform.api.config_access import get_question_voice_settings
from app.question_voice.domain.tts_exceptions import QuestionVoiceDisabledError
from app.question_voice.services.tts_cache import TtsCacheService
from app.shared.infrastructure.models import Answer, Interview


async def get_question_audio_path(
    interview_id: str,
    answer_id: int | None = None,
) -> Path:
    """Return a WAV path for interview question audio.

    Args:
        interview_id: Interview session UUID.
        answer_id: Optional answer row id; defaults to the current question.

    Returns:
        Path to a cached or newly synthesized WAV file.

    Raises:
        QuestionVoiceDisabledError: When voice is disabled in config.
        InterviewNotFoundError: When the interview does not exist.
        InterviewNotActiveError: When the session is not active.
        ValueError: When no suitable unanswered answer exists.
        QuestionVoiceSynthesisError: When synthesis cannot complete.
    """
    voice_settings = get_question_voice_settings()
    if voice_settings is None:
        raise QuestionVoiceDisabledError()

    interview = load_interview_or_raise(interview_id)
    require_active(interview_view(interview))
    answer = _resolve_answer(interview, answer_id)
    return await TtsCacheService.get_or_fetch(
        voice_settings.voice_id,
        interview.locale,
        answer.question_text,
    )


def _resolve_answer(
    interview: Interview,
    answer_id: int | None,
) -> Answer:
    """Pick the target answer row for audio synthesis.

    Args:
        interview: Interview with loaded answers.
        answer_id: Optional answer primary key; defaults to first unanswered.

    Returns:
        Answer row with ``question_text`` to synthesize.

    Raises:
        ValueError: If no suitable unanswered answer exists.
    """
    if answer_id is not None:
        for answer in interview.answers:
            if answer.id == answer_id:
                if answer.answer_text is not None:
                    raise ValueError("Answer is already submitted")
                if not answer.question_text.strip():
                    raise ValueError("Question text is empty")
                return answer
        raise ValueError(f"Answer not found in interview: {answer_id}")

    current = get_current_unanswered(interview)
    if current is None:
        raise ValueError("No unanswered question in this interview")
    for answer in interview.answers:
        if answer.question_id == current.question_id and answer.round == current.round:
            if not answer.question_text.strip():
                raise ValueError("Question text is empty")
            return answer
    raise ValueError("No unanswered question in this interview")
