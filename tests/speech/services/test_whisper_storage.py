# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Whisper on-disk storage helpers."""

from unittest.mock import patch

import pytest

from app.speech.services.whisper_storage import (
    is_installed,
    is_valid_model_dir,
    model_dir,
)


class TestModelDir:
    """Tests for model_dir path helper."""

    def test_returns_correct_path(self, tmp_path):
        """model_dir returns the expected path under whisper-models root."""
        with patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path):
            result = model_dir("small")
            assert result == tmp_path / "small"

    def test_normalizes_size(self, tmp_path):
        """model_dir normalizes the size parameter."""
        with patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path):
            result = model_dir(" SMALL ")
            assert result == tmp_path / "small"

    def test_invalid_size_raises(self, tmp_path):
        """model_dir raises ValueError for unsupported sizes."""
        with (
            patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path),
            pytest.raises(ValueError, match="Unsupported speech model size"),
        ):
            model_dir("huge")


class TestIsValidModelDir:
    """Tests for is_valid_model_dir validator."""

    def test_valid_directory_with_model_bin(self, tmp_path):
        """Returns True when directory contains model.bin."""
        model_path = tmp_path / "small"
        model_path.mkdir()
        (model_path / "model.bin").write_bytes(b"fake-model")
        assert is_valid_model_dir(model_path) is True

    def test_missing_model_bin(self, tmp_path):
        """Returns False when model.bin is absent."""
        model_path = tmp_path / "small"
        model_path.mkdir()
        assert is_valid_model_dir(model_path) is False

    def test_empty_directory(self, tmp_path):
        """Returns False for an empty directory."""
        model_path = tmp_path / "small"
        model_path.mkdir()
        assert is_valid_model_dir(model_path) is False

    def test_directory_with_other_files(self, tmp_path):
        """Returns False when only other files exist."""
        model_path = tmp_path / "small"
        model_path.mkdir()
        (model_path / "config.json").write_text("{}")
        assert is_valid_model_dir(model_path) is False

    def test_not_a_directory(self, tmp_path):
        """Returns False when path is a file, not a directory."""
        file_path = tmp_path / "small"
        file_path.write_bytes(b"not-a-dir")
        assert is_valid_model_dir(file_path) is False

    def test_nonexistent_path(self, tmp_path):
        """Returns False when path does not exist."""
        missing_path = tmp_path / "small" / "nonexistent"
        assert is_valid_model_dir(missing_path) is False


class TestIsInstalled:
    """Tests for is_installed helper."""

    def test_returns_true_when_installed(self, tmp_path):
        """is_installed returns True when model.bin exists."""
        model_path = tmp_path / "small"
        model_path.mkdir()
        (model_path / "model.bin").write_bytes(b"fake-model")

        with patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path):
            assert is_installed("small") is True

    def test_returns_false_when_missing(self, tmp_path):
        """is_installed returns False when directory does not exist."""
        with patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path):
            assert is_installed("small") is False

    def test_returns_false_when_no_model_bin(self, tmp_path):
        """is_installed returns False when model.bin is absent."""
        model_path = tmp_path / "medium"
        model_path.mkdir()
        (model_path / "other.file").write_text("data")

        with patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path):
            assert is_installed("medium") is False

    def test_normalizes_size(self, tmp_path):
        """is_installed normalizes the size parameter."""
        model_path = tmp_path / "large"
        model_path.mkdir()
        (model_path / "model.bin").write_bytes(b"fake-model")

        with patch("app.speech.services.whisper_storage.WHISPER_MODELS_ROOT", tmp_path):
            assert is_installed("LARGE") is True
