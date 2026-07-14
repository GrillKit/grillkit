# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for AI error message formatting."""

from app.interview.services.ai_errors import ai_error_message_for_client


class TestModelNotFound:
    """Tests for model-not-found error messages."""

    def test_exact_match_lowercase(self) -> None:
        exc = Exception("model 'gpt-4' not found on endpoint")
        result = ai_error_message_for_client(exc)
        assert "AI model is not available" in result
        assert "/config" in result

    def test_mixed_case(self) -> None:
        exc = Exception("Model Not Found")
        result = ai_error_message_for_client(exc)
        assert "AI model is not available" in result

    def test_model_before_not_found(self) -> None:
        exc = Exception("the requested model was not found")
        result = ai_error_message_for_client(exc)
        assert "AI model is not available" in result


class TestTimeout:
    """Tests for timeout error messages."""

    def test_timed_out(self) -> None:
        exc = Exception("request timed out after 30 seconds")
        result = ai_error_message_for_client(exc)
        assert "AI evaluation timed out" in result
        assert "/config" in result

    def test_timeout_keyword(self) -> None:
        exc = Exception("Connection timeout")
        result = ai_error_message_for_client(exc)
        assert "AI evaluation timed out" in result

    def test_timeout_mixed_case(self) -> None:
        exc = Exception("Timeout Error")
        result = ai_error_message_for_client(exc)
        assert "AI evaluation timed out" in result


class TestGenericError:
    """Tests for generic error messages."""

    def test_returns_prefixed_message(self) -> None:
        exc = Exception("Something went wrong")
        result = ai_error_message_for_client(exc)
        assert result == "AI evaluation failed: Something went wrong"

    def test_empty_message(self) -> None:
        exc = Exception("")
        result = ai_error_message_for_client(exc)
        assert result == "AI evaluation failed: "

    def test_long_message(self) -> None:
        msg = "A" * 500
        exc = Exception(msg)
        result = ai_error_message_for_client(exc)
        assert result == f"AI evaluation failed: {msg}"


class TestEdgeCases:
    """Tests for edge cases in error matching."""

    def test_model_found_but_not_other_word(self) -> None:
        exc = Exception("model updated successfully")
        result = ai_error_message_for_client(exc)
        assert "AI evaluation failed" in result

    def test_not_found_without_model(self) -> None:
        exc = Exception("page not found")
        result = ai_error_message_for_client(exc)
        assert "AI evaluation failed" in result

    def test_both_keywords_present_prefers_model(self) -> None:
        exc = Exception("model 'xyz' not found and timed out")
        result = ai_error_message_for_client(exc)
        assert "AI model is not available" in result
