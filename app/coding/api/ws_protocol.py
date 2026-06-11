# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket wire protocol mapping for coding sessions."""

from typing import Any

from app.coding.schemas.ws import (
    CodingFeedbackMessage,
    CodingSavedMessage,
    EvaluatingMessage,
    coding_server_message_to_dict,
)
from app.coding.services.events import CodingFeedbackEvent
from app.interview.services.events import (
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewEvent,
)


def coding_event_to_message(
    event: InterviewEvent | CodingFeedbackEvent,
) -> dict[str, Any]:
    """Convert a semantic service event to a coding WebSocket JSON message.

    Args:
        event: Event from coding submission services.

    Returns:
        JSON-serializable message dict for the client.

    Raises:
        TypeError: If the event type is not supported.
    """
    if isinstance(event, AnswerSavedEvent):
        return coding_server_message_to_dict(CodingSavedMessage())
    if isinstance(event, EvaluatingEvent):
        return coding_server_message_to_dict(EvaluatingMessage())
    if isinstance(event, CodingFeedbackEvent):
        return coding_server_message_to_dict(
            CodingFeedbackMessage(
                task_id=event.task_id,
                order=event.order,
                round=event.round,
                follow_up_question=event.follow_up_text
                if event.follow_up_needed
                else None,
                follow_up_mode=event.follow_up_mode,
                next_task=event.next_task,
                feedback=event.feedback,
                timer_remaining_seconds=event.timer_remaining_seconds,
            )
        )
    msg = f"Unsupported coding event: {type(event)!r}"
    raise TypeError(msg)
