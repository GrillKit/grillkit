# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding WebSocket session service."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.coding.api.ws_session import CodingWebSocketService
from app.coding.domain.exceptions import CodingTaskNotCurrentError
from app.coding.services.events import CodingFeedbackEvent
from app.interview.services.events import AnswerSavedEvent, EvaluatingEvent
from tests.fakes import FakeProvider


def _make_submission_service(
    *,
    submit_events: tuple | None = None,
    timeout_events: tuple | None = None,
) -> Mock:
    """Build a mock submission service that yields predetermined events."""
    service = Mock()

    async def _stream_submit(**_kwargs):
        for event in submit_events or ():
            yield event

    async def _stream_timeout_submission(**_kwargs):
        for event in timeout_events or ():
            yield event

    service.stream_submit = _stream_submit
    service.stream_timeout_submission = MagicMock(wraps=_stream_timeout_submission)
    return service


class TestCodingWebSocketServiceIterResponses:
    """Tests for ``CodingWebSocketService.iter_responses``."""

    @pytest.mark.asyncio
    async def test_iter_responses_dispatches_submit(self) -> None:
        """iter_responses with type ``submit`` dispatches to _handle_submit."""
        service = _make_submission_service(
            submit_events=(
                AnswerSavedEvent(),
                EvaluatingEvent(),
                CodingFeedbackEvent(
                    task_id="cod-001",
                    order=1,
                    round=0,
                    follow_up_needed=False,
                    follow_up_text=None,
                    follow_up_mode=None,
                    next_task=None,
                    feedback="Nice.",
                ),
            ),
        )
        provider = FakeProvider(replies=[])
        messages = []
        async for msg in CodingWebSocketService.iter_responses(
            {"type": "submit", "task_id": "cod-001", "source_code": "pass"},
            interview_id="iv-001",
            provider=provider,
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 3
        assert messages[0]["type"] == "saved"
        assert messages[1]["type"] == "evaluating"
        assert messages[2]["type"] == "feedback"
        assert messages[2]["task_id"] == "cod-001"
        assert messages[2]["feedback"] == "Nice."

    @pytest.mark.asyncio
    async def test_iter_responses_dispatches_timeout(self) -> None:
        """iter_responses with type ``timeout`` dispatches to _handle_timeout."""
        service = _make_submission_service(
            timeout_events=(
                CodingFeedbackEvent(
                    task_id="cod-001",
                    order=1,
                    round=0,
                    follow_up_needed=False,
                    follow_up_text=None,
                    follow_up_mode=None,
                    next_task=None,
                    feedback="Time expired.",
                ),
            ),
        )
        messages = []
        async for msg in CodingWebSocketService.iter_responses(
            {"type": "timeout", "task_id": "cod-001", "round": 0},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "feedback"
        assert messages[0]["feedback"] == "Time expired."

    @pytest.mark.asyncio
    async def test_iter_responses_returns_error_for_unknown_type(self) -> None:
        """iter_responses returns an error for unknown message types."""
        messages = []
        async for msg in CodingWebSocketService.iter_responses(
            {"type": "unknown"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=AsyncMock(),  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "Unknown message type" in messages[0]["message"]


class TestCodingWebSocketServiceHandleSubmit:
    """Tests for ``CodingWebSocketService._handle_submit``."""

    @pytest.mark.asyncio
    async def test_handle_submit_validates_task_id_required(self) -> None:
        """_handle_submit yields error when task_id is missing."""
        messages = []
        async for msg in CodingWebSocketService._handle_submit(
            {"type": "submit", "source_code": "pass"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=AsyncMock(),  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "task_id and source_code are required" in messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_submit_validates_source_code_required(self) -> None:
        """_handle_submit yields error when source_code is missing."""
        messages = []
        async for msg in CodingWebSocketService._handle_submit(
            {"type": "submit", "task_id": "cod-001"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=AsyncMock(),  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "task_id and source_code are required" in messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_submit_validates_empty_task_id(self) -> None:
        """_handle_submit yields error when task_id is empty after strip."""
        messages = []
        async for msg in CodingWebSocketService._handle_submit(
            {"type": "submit", "task_id": "   ", "source_code": "pass"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=AsyncMock(),  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_handle_submit_yields_events_from_submission_service(self) -> None:
        """_handle_submit yields events produced by the submission service."""
        service = _make_submission_service(
            submit_events=(
                AnswerSavedEvent(),
                EvaluatingEvent(),
                CodingFeedbackEvent(
                    task_id="cod-001",
                    order=1,
                    round=0,
                    follow_up_needed=False,
                    follow_up_text=None,
                    follow_up_mode=None,
                    next_task=None,
                    feedback="Great.",
                ),
            ),
        )
        messages = []
        async for msg in CodingWebSocketService._handle_submit(
            {"type": "submit", "task_id": "cod-001", "source_code": "pass"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 3
        assert messages[0]["type"] == "saved"
        assert messages[1]["type"] == "evaluating"
        assert messages[2]["type"] == "feedback"
        assert messages[2]["feedback"] == "Great."

    @pytest.mark.asyncio
    async def test_handle_submit_handles_domain_errors(self) -> None:
        """_handle_submit yields a domain error payload on CodingDomainError."""
        service = AsyncMock()

        async def _failing_stream(**_kwargs):
            raise CodingTaskNotCurrentError("iv-001", "cod-001")
            yield  # type: ignore[unreachable]

        service.stream_submit = _failing_stream
        messages = []
        async for msg in CodingWebSocketService._handle_submit(
            {"type": "submit", "task_id": "cod-001", "source_code": "pass"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "not the current coding task" in messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_submit_handles_general_exceptions(self) -> None:
        """_handle_submit yields a generic error payload on unexpected exceptions."""
        service = AsyncMock()

        async def _failing_stream(**_kwargs):
            raise RuntimeError("boom")
            yield  # type: ignore[unreachable]

        service.stream_submit = _failing_stream
        messages = []
        async for msg in CodingWebSocketService._handle_submit(
            {"type": "submit", "task_id": "cod-001", "source_code": "pass"},
            interview_id="iv-001",
            provider=FakeProvider(replies=[]),
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"


class TestCodingWebSocketServiceHandleTimeout:
    """Tests for ``CodingWebSocketService._handle_timeout``."""

    @pytest.mark.asyncio
    async def test_handle_timeout_validates_task_id_required(self) -> None:
        """_handle_timeout yields error when task_id is missing."""
        messages = []
        async for msg in CodingWebSocketService._handle_timeout(
            {"type": "timeout", "round": 0},
            interview_id="iv-001",
            submission_service=AsyncMock(),  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "task_id and round are required" in messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_timeout_validates_round_required(self) -> None:
        """_handle_timeout yields error when round is missing."""
        messages = []
        async for msg in CodingWebSocketService._handle_timeout(
            {"type": "timeout", "task_id": "cod-001"},
            interview_id="iv-001",
            submission_service=AsyncMock(),  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "task_id and round are required" in messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_timeout_uses_question_id_fallback(self) -> None:
        """_handle_timeout falls back to ``question_id`` when ``task_id`` is absent."""
        service = _make_submission_service(
            timeout_events=(
                CodingFeedbackEvent(
                    task_id="cod-001",
                    order=1,
                    round=0,
                    follow_up_needed=False,
                    follow_up_text=None,
                    follow_up_mode=None,
                    next_task=None,
                    feedback="Timeout.",
                ),
            ),
        )
        messages = []
        async for msg in CodingWebSocketService._handle_timeout(
            {"type": "timeout", "question_id": "cod-001", "round": 0},
            interview_id="iv-001",
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "feedback"
        assert messages[0]["feedback"] == "Timeout."

    @pytest.mark.asyncio
    async def test_handle_timeout_yields_events_from_submission_service(self) -> None:
        """_handle_timeout yields events produced by the submission service."""
        service = _make_submission_service(
            timeout_events=(
                CodingFeedbackEvent(
                    task_id="cod-001",
                    order=1,
                    round=0,
                    follow_up_needed=False,
                    follow_up_text=None,
                    follow_up_mode=None,
                    next_task=None,
                    feedback="Time expired.",
                ),
            ),
        )
        messages = []
        async for msg in CodingWebSocketService._handle_timeout(
            {"type": "timeout", "task_id": "cod-001", "round": 0},
            interview_id="iv-001",
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "feedback"
        assert messages[0]["feedback"] == "Time expired."
        service.stream_timeout_submission.assert_called_once_with(
            interview_id="iv-001",
            task_id="cod-001",
            round_num=0,
        )

    @pytest.mark.asyncio
    async def test_handle_timeout_handles_domain_errors(self) -> None:
        """_handle_timeout yields a domain error payload on CodingDomainError."""
        service = AsyncMock()

        async def _failing_stream(**_kwargs):
            raise CodingTaskNotCurrentError("iv-001", "cod-001")
            yield  # type: ignore[unreachable]

        service.stream_timeout_submission = _failing_stream
        messages = []
        async for msg in CodingWebSocketService._handle_timeout(
            {"type": "timeout", "task_id": "cod-001", "round": 0},
            interview_id="iv-001",
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert "not the current coding task" in messages[0]["message"]

    @pytest.mark.asyncio
    async def test_handle_timeout_handles_general_exceptions(self) -> None:
        """_handle_timeout yields a generic error payload on unexpected exceptions."""
        service = AsyncMock()

        async def _failing_stream(**_kwargs):
            raise RuntimeError("boom")
            yield  # type: ignore[unreachable]

        service.stream_timeout_submission = _failing_stream
        messages = []
        async for msg in CodingWebSocketService._handle_timeout(
            {"type": "timeout", "task_id": "cod-001", "round": 0},
            interview_id="iv-001",
            submission_service=service,  # type: ignore[arg-type]
        ):
            messages.append(msg)

        assert len(messages) == 1
        assert messages[0]["type"] == "error"
