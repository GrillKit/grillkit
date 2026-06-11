# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket server message schemas for coding sessions."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.interview.schemas.ws import EvaluatingMessage, server_message_to_dict


class CodingSavedMessage(BaseModel):
    """Server message emitted after coding submission text is persisted."""

    model_config = ConfigDict(frozen=True)

    type: Literal["saved"] = "saved"


class CodingFeedbackMessage(BaseModel):
    """Server message with evaluation feedback for one coding task round."""

    model_config = ConfigDict(frozen=True)

    type: Literal["feedback"] = "feedback"
    task_id: str
    order: int
    round: int
    follow_up_question: str | None
    follow_up_mode: Literal["code", "explanation"] | None = None
    next_task: dict[str, Any] | None = None
    feedback: str | None = None
    timer_remaining_seconds: int | None = None


def coding_server_message_to_dict(message: BaseModel) -> dict[str, Any]:
    """Serialize a coding WebSocket server message for ``send_json``.

    Args:
        message: Pydantic server message model.

    Returns:
        JSON-serializable dict.
    """
    if isinstance(message, CodingFeedbackMessage):
        payload = message.model_dump(mode="json")
        if payload.get("feedback") is None:
            payload.pop("feedback", None)
        if payload.get("timer_remaining_seconds") is None:
            payload.pop("timer_remaining_seconds", None)
        if payload.get("follow_up_mode") is None:
            payload.pop("follow_up_mode", None)
        if payload.get("next_task") is None:
            payload.pop("next_task", None)
        return payload
    return server_message_to_dict(message)


__all__ = [
    "CodingFeedbackMessage",
    "CodingSavedMessage",
    "EvaluatingMessage",
    "coding_server_message_to_dict",
]
