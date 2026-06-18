# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding WebSocket protocol mapping."""

import pytest

from app.coding.api.ws_protocol import coding_event_to_message
from app.coding.services.events import CodingFeedbackEvent
from app.interview.services.events import AnswerSavedEvent, EvaluatingEvent


def test_coding_event_to_message_answer_saved_event() -> None:
    """coding_event_to_message maps AnswerSavedEvent to saved message."""
    event = AnswerSavedEvent()
    message = coding_event_to_message(event)
    assert message == {"type": "saved"}


def test_coding_event_to_message_evaluating_event() -> None:
    """coding_event_to_message maps EvaluatingEvent to evaluating message."""
    event = EvaluatingEvent()
    message = coding_event_to_message(event)
    assert message == {"type": "evaluating"}


def test_coding_event_to_message_coding_feedback_event_with_all_fields() -> None:
    """coding_event_to_message maps CodingFeedbackEvent with all fields correctly."""
    event = CodingFeedbackEvent(
        task_id="cod-001",
        order=1,
        round=0,
        follow_up_needed=True,
        follow_up_text="Add type hints.",
        follow_up_mode="code",
        next_task={"task_id": "cod-002", "prompt_text": "Next task."},
        feedback="Good effort.",
        timer_remaining_seconds=45,
    )
    message = coding_event_to_message(event)
    assert message["type"] == "feedback"
    assert message["task_id"] == "cod-001"
    assert message["order"] == 1
    assert message["round"] == 0
    assert message["follow_up_question"] == "Add type hints."
    assert message["follow_up_mode"] == "code"
    assert message["next_task"] == {"task_id": "cod-002", "prompt_text": "Next task."}
    assert message["feedback"] == "Good effort."
    assert message["timer_remaining_seconds"] == 45


def test_coding_event_to_message_coding_feedback_event_without_follow_up() -> None:
    """coding_event_to_message maps CodingFeedbackEvent without follow-up correctly."""
    event = CodingFeedbackEvent(
        task_id="cod-001",
        order=1,
        round=0,
        follow_up_needed=False,
        follow_up_text=None,
        follow_up_mode=None,
        next_task=None,
        feedback="Excellent work.",
        timer_remaining_seconds=None,
    )
    message = coding_event_to_message(event)
    assert message["type"] == "feedback"
    assert message["task_id"] == "cod-001"
    assert message["order"] == 1
    assert message["round"] == 0
    assert "follow_up_mode" not in message
    assert "next_task" not in message
    assert "timer_remaining_seconds" not in message
    assert message["feedback"] == "Excellent work."
    assert message["follow_up_question"] is None


def test_coding_event_to_message_raises_type_error_for_unknown_event() -> None:
    """coding_event_to_message raises TypeError for unsupported event types."""
    # Use a simple object that is not a known event type
    class UnknownEvent:
        pass

    with pytest.raises(TypeError, match="Unsupported coding event"):
        coding_event_to_message(UnknownEvent())  # type: ignore[arg-type]
