# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for interview domain error HTTP mapping."""

from fastapi import HTTPException
import pytest

from app.interview.api.errors import http_exception_from_domain_error, ws_error_payload
from app.shared.domain.exceptions import (
    AnswerNotFoundError,
    InterviewNotActiveError,
    InterviewNotFoundError,
    UnansweredAnswerNotFoundError,
)


def test_ws_error_payload():
    """ws_error_payload wraps domain errors for WebSocket clients."""
    exc = InterviewNotFoundError("id-1")
    assert ws_error_payload(exc) == {
        "type": "error",
        "message": "Interview not found: id-1",
    }


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (InterviewNotFoundError("id-1"), 404),
        (AnswerNotFoundError("id-1", "q1", 0), 404),
        (InterviewNotActiveError("id-1"), 400),
        (UnansweredAnswerNotFoundError("id-1", "q1"), 400),
    ],
)
def test_http_exception_from_domain_error(exc, status_code):
    """Domain errors map to expected HTTP status codes."""
    http_exc = http_exception_from_domain_error(exc)
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == status_code
    assert http_exc.detail == str(exc)
