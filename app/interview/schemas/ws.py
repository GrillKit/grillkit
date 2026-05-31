# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket server message schemas for interview sessions."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AnswerSavedMessage(BaseModel):
    """Server message emitted after answer text is persisted."""

    model_config = ConfigDict(frozen=True)

    type: Literal["saved"] = "saved"


class EvaluatingMessage(BaseModel):
    """Server message emitted when AI evaluation starts."""

    model_config = ConfigDict(frozen=True)

    type: Literal["evaluating"] = "evaluating"


class TranscriptMessage(BaseModel):
    """Server message with Whisper transcript for an audio answer."""

    model_config = ConfigDict(frozen=True)

    type: Literal["transcript"] = "transcript"
    question_id: str
    round: int
    text: str


class AnswerFeedbackMessage(BaseModel):
    """Server message with evaluation feedback for one answer round."""

    model_config = ConfigDict(frozen=True)

    type: Literal["feedback"] = "feedback"
    question_id: str
    order: int
    round: int
    follow_up_question: str | None
    next_question: dict[str, Any] | None
    timed_out: bool = False
    feedback: str | None = None
    timer_remaining_seconds: int | None = None


class InterviewCompletedMessage(BaseModel):
    """Server message when the entire interview session is complete."""

    model_config = ConfigDict(frozen=True)

    type: Literal["interview_completed"] = "interview_completed"
    overall_feedback: dict[str, Any]
    score: int
    max_score: int


def server_message_to_dict(message: BaseModel) -> dict[str, Any]:
    """Serialize a server WebSocket message for ``send_json``.

    Args:
        message: Pydantic server message model.

    Returns:
        JSON-serializable dict. Feedback messages always include
        ``follow_up_question`` and ``next_question`` (may be null); only
        ``feedback`` and ``timer_remaining_seconds`` are omitted when unset.
    """
    if isinstance(message, AnswerFeedbackMessage):
        payload = message.model_dump(mode="json")
        if payload.get("feedback") is None:
            payload.pop("feedback", None)
        if payload.get("timer_remaining_seconds") is None:
            payload.pop("timer_remaining_seconds", None)
        return payload
    return message.model_dump(mode="json")
