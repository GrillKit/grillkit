# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Piper voice on-disk validation."""

from pathlib import Path

from app.question_voice.services.piper_storage import is_valid_voice_dir


def test_is_valid_voice_dir_accepts_staging_directory(tmp_path: Path) -> None:
    """Staging dirs use a ``.staging-`` prefix; validation must use voice_id."""
    voice_id = "ru_RU-dmitri-medium"
    staging = tmp_path / f".staging-{voice_id}"
    staging.mkdir()
    (staging / f"{voice_id}.onnx").write_bytes(b"onnx")
    (staging / f"{voice_id}.onnx.json").write_text("{}")

    assert is_valid_voice_dir(staging, voice_id) is True


def test_is_valid_voice_dir_rejects_missing_files(tmp_path: Path) -> None:
    """Validation fails when model files are absent."""
    voice_id = "en_US-lessac-medium"
    directory = tmp_path / voice_id
    directory.mkdir()

    assert is_valid_voice_dir(directory, voice_id) is False
