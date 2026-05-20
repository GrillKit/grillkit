# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket JSON protocol mapping for interview sessions."""

from typing import Any

from app.services.interview_events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewCompletedEvent,
    InterviewEvent,
)


def event_to_message(event: InterviewEvent) -> dict[str, Any]:
    """Convert a semantic interview event to a WebSocket JSON message.

    Args:
        event: Domain event from the application service layer.

    Returns:
        JSON-serializable message dict for the client.
    """
    if isinstance(event, AnswerSavedEvent):
        return {"type": "saved"}
    if isinstance(event, EvaluatingEvent):
        return {"type": "evaluating"}
    if isinstance(event, AnswerFeedbackEvent):
        return {
            "type": "feedback",
            "question_id": event.question_id,
            "order": event.order,
            "round": event.round,
            "follow_up_question": event.follow_up_text
            if event.follow_up_needed
            else None,
            "next_question": event.next_question,
        }
    if isinstance(event, InterviewCompletedEvent):
        return {
            "type": "interview_completed",
            "overall_feedback": event.overall_feedback,
            "score": event.score,
            "max_score": event.max_score,
        }
    raise TypeError(f"Unsupported interview event: {type(event)!r}")


def events_to_messages(events: list[InterviewEvent]) -> list[dict[str, Any]]:
    """Convert a sequence of domain events to WebSocket messages.

    Args:
        events: Events returned by application services.

    Returns:
        List of JSON message dicts in the same order.
    """
    return [event_to_message(event) for event in events]
