# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket JSON protocol mapping for interview sessions."""

from typing import Any

from app.interview.schemas.ws import (
    AnswerFeedbackMessage,
    AnswerSavedMessage,
    EvaluatingMessage,
    InterviewCompletedMessage,
    TranscriptMessage,
    server_message_to_dict,
)
from app.interview.services.events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewCompletedEvent,
    InterviewEvent,
    TranscriptEvent,
)


def server_message_from_event(
    event: InterviewEvent,
) -> (
    AnswerSavedMessage
    | EvaluatingMessage
    | TranscriptMessage
    | AnswerFeedbackMessage
    | InterviewCompletedMessage
):
    """Map a semantic service event to a typed WebSocket message.

    Args:
        event: Event from answer or completion services.

    Returns:
        Pydantic message model for JSON serialization.

    Raises:
        TypeError: If the event type is not supported.
    """
    if isinstance(event, AnswerSavedEvent):
        return AnswerSavedMessage()
    if isinstance(event, EvaluatingEvent):
        return EvaluatingMessage()
    if isinstance(event, TranscriptEvent):
        return TranscriptMessage(
            question_id=event.question_id,
            round=event.round,
            text=event.text,
        )
    if isinstance(event, AnswerFeedbackEvent):
        return AnswerFeedbackMessage(
            question_id=event.question_id,
            order=event.order,
            round=event.round,
            follow_up_question=event.follow_up_text if event.follow_up_needed else None,
            next_question=event.next_question,
            timed_out=event.timed_out,
            feedback=event.feedback,
            timer_remaining_seconds=event.timer_remaining_seconds,
        )
    if isinstance(event, InterviewCompletedEvent):
        return InterviewCompletedMessage(
            overall_feedback=event.overall_feedback,
            score=event.score,
            max_score=event.max_score,
        )
    raise TypeError(f"Unsupported interview event: {type(event)!r}")


def event_to_message(event: InterviewEvent) -> dict[str, Any]:
    """Convert a semantic interview event to a WebSocket JSON message.

    Args:
        event: Domain event from the application service layer.

    Returns:
        JSON-serializable message dict for the client.
    """
    return server_message_to_dict(server_message_from_event(event))


def events_to_messages(events: list[InterviewEvent]) -> list[dict[str, Any]]:
    """Convert a sequence of domain events to WebSocket messages.

    Args:
        events: Events returned by application services.

    Returns:
        List of JSON message dicts in the same order.
    """
    return [event_to_message(event) for event in events]
