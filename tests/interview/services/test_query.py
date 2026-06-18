# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for InterviewQuery read-only service."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.interview.domain.entities import Interview
from app.interview.domain.exceptions import InterviewNotFoundError
from app.interview.domain.value_objects import (
    SessionSelection,
    TrackSelection,
)
from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.interview.services.query import InterviewQuery


def _make_interview_read(
    *,
    status: str = "active",
    answers: list[AnswerRead] | None = None,
) -> InterviewRead:
    return InterviewRead(
        id="iv-1",
        status=status,
        locale="en",
        selection_spec="{}",
        question_ids='["q1","q2"]',
        question_count=2,
        question_time_limit_seconds=None,
        answers=answers if answers is not None else [
            AnswerRead(
                id=1,
                question_id="q1",
                order=1,
                round=0,
                question_text="Q1",
                question_code=None,
                answer_text=None,
                score=None,
                started_at=None,
            ),
            AnswerRead(
                id=2,
                question_id="q2",
                order=2,
                round=0,
                question_text="Q2",
                question_code=None,
                answer_text="answered",
                score=4,
                started_at=None,
            ),
        ],
    )


def _make_active_shell() -> Interview:
    return Interview.start_shell(
        "iv-1",
        selection=SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        locale="en",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestGetInterview:
    """Tests for InterviewQuery.get_interview."""

    def test_get_interview_loads_with_tasks(self) -> None:
        uow = MagicMock()
        read = _make_interview_read()
        with patch(
            "app.interview.services.query.load_interview_read",
            return_value=read,
        ) as mock_load:
            query = InterviewQuery(uow)
            result = query.get_interview("iv-1")
        mock_load.assert_called_once_with(uow, "iv-1")
        assert result is read

    def test_get_interview_returns_none_when_not_found(self) -> None:
        uow = MagicMock()
        with patch(
            "app.interview.services.query.load_interview_read",
            return_value=None,
        ) as mock_load:
            query = InterviewQuery(uow)
            result = query.get_interview("missing")
        mock_load.assert_called_once_with(uow, "missing")
        assert result is None


class TestLoad:
    """Tests for InterviewQuery.load static method."""

    def test_load_returns_interview(self) -> None:
        read = _make_interview_read()
        with patch(
            "app.interview.services.query.load_interview_read",
            return_value=read,
        ) as mock_load:
            result = InterviewQuery.load("iv-1")
        assert result is read
        assert mock_load.call_args[0][1] == "iv-1"

    def test_load_returns_none_when_not_found(self) -> None:
        with patch(
            "app.interview.services.query.load_interview_read",
            return_value=None,
        ):
            assert InterviewQuery.load("missing") is None


class TestGetActiveOrRaise:
    """Tests for InterviewQuery.get_active_or_raise."""

    def test_returns_active_interview(self) -> None:
        uow = MagicMock()
        shell = _make_active_shell()
        uow.interviews.get_aggregate.return_value = shell
        read = _make_interview_read()
        with patch(
            "app.interview.services.query.load_interview_read",
            return_value=read,
        ):
            query = InterviewQuery(uow)
            result = query.get_active_or_raise("iv-1")
        assert result is read
        uow.interviews.get_aggregate.assert_called_once_with("iv-1")

    def test_raises_when_interview_not_found(self) -> None:
        uow = MagicMock()
        uow.interviews.get_aggregate.return_value = None
        query = InterviewQuery(uow)
        with pytest.raises(InterviewNotFoundError):
            query.get_active_or_raise("missing")

    def test_raises_when_interview_not_active(self) -> None:
        uow = MagicMock()
        shell = _make_active_shell().with_session_completed(
            {"overall_feedback": "done"}
        )
        uow.interviews.get_aggregate.return_value = shell
        query = InterviewQuery(uow)
        with pytest.raises(Exception):
            query.get_active_or_raise("iv-1")

    def test_raises_when_load_returns_none(self) -> None:
        uow = MagicMock()
        shell = _make_active_shell()
        uow.interviews.get_aggregate.return_value = shell
        with patch(
            "app.interview.services.query.load_interview_read",
            return_value=None,
        ):
            query = InterviewQuery(uow)
            with pytest.raises(InterviewNotFoundError):
                query.get_active_or_raise("iv-1")


class TestGetCurrentUnanswered:
    """Tests for InterviewQuery.get_current_unanswered."""

    def test_returns_first_unanswered_answer(self) -> None:
        read = _make_interview_read()
        result = InterviewQuery.get_current_unanswered(read)
        assert result is not None
        assert result.question_id == "q1"

    def test_returns_none_when_all_answered(self) -> None:
        read = _make_interview_read(
            answers=[
                AnswerRead(
                    id=1,
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q1",
                    question_code=None,
                    answer_text="done",
                    score=4,
                    started_at=None,
                ),
            ]
        )
        assert InterviewQuery.get_current_unanswered(read) is None

    def test_returns_none_for_empty_answers(self) -> None:
        read = _make_interview_read(answers=[])
        assert InterviewQuery.get_current_unanswered(read) is None
