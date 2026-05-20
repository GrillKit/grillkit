# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for WebSocket protocol mapping."""

from app.api.ws_protocol import event_to_message, events_to_messages
from app.services.interview_events import (
    AnswerFeedbackEvent,
    AnswerSavedEvent,
    EvaluatingEvent,
    InterviewCompletedEvent,
)


def test_event_to_message_saved():
    """Test AnswerSavedEvent maps to saved message."""
    assert event_to_message(AnswerSavedEvent()) == {"type": "saved"}


def test_event_to_message_feedback():
    """Test AnswerFeedbackEvent maps to feedback message."""
    message = event_to_message(
        AnswerFeedbackEvent(
            question_id="q1",
            order=1,
            round=0,
            follow_up_needed=True,
            follow_up_text="Why?",
            next_question=None,
        )
    )
    assert message["type"] == "feedback"
    assert message["follow_up_question"] == "Why?"


def test_events_to_messages_preserves_order():
    """Test events_to_messages keeps event order."""
    messages = events_to_messages(
        [AnswerSavedEvent(), EvaluatingEvent(), InterviewCompletedEvent({}, 3, 15)]
    )
    assert [m["type"] for m in messages] == [
        "saved",
        "evaluating",
        "interview_completed",
    ]
