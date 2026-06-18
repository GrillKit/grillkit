# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for WhisperReadinessService."""

from unittest.mock import patch

import pytest

from app.speech.services.readiness import WhisperReadinessService


class TestWhisperReadinessService:
    """Tests for WhisperReadinessService checks."""

    def test_is_model_installed_true(self):
        """Returns True when model is installed on disk."""
        with patch(
            "app.speech.services.readiness.is_installed", return_value=True
        ) as mock_installed:
            result = WhisperReadinessService.is_model_installed("small")

        assert result is True
        mock_installed.assert_called_once_with("small")

    def test_is_model_installed_false(self):
        """Returns False when model is not installed."""
        with patch(
            "app.speech.services.readiness.is_installed", return_value=False
        ) as mock_installed:
            result = WhisperReadinessService.is_model_installed("medium")

        assert result is False
        mock_installed.assert_called_once_with("medium")

    def test_normalizes_size(self):
        """Normalizes the speech model size before checking."""
        with patch(
            "app.speech.services.readiness.is_installed", return_value=True
        ) as mock_installed:
            result = WhisperReadinessService.is_model_installed(" LARGE ")

        assert result is True
        mock_installed.assert_called_once_with("large")

    def test_invalid_size_raises(self):
        """Raises ValueError for unsupported model sizes."""
        with pytest.raises(ValueError, match="Unsupported speech model size"):
            WhisperReadinessService.is_model_installed("huge")
