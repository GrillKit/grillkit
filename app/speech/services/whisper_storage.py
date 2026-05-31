# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""On-disk paths and validation for installed Whisper models."""

from pathlib import Path

from app.paths import WHISPER_MODELS_ROOT
from app.speech.services.rules.speech_models import normalize_speech_model_size


def model_dir(size: str) -> Path:
    """Return the installation directory for a speech model size."""
    code = normalize_speech_model_size(size)
    return WHISPER_MODELS_ROOT / code


def is_valid_model_dir(path: Path) -> bool:
    """Return whether ``path`` contains a faster-whisper model snapshot."""
    if not path.is_dir():
        return False
    return (path / "model.bin").is_file()


def is_installed(size: str) -> bool:
    """Return whether a valid model is present for the size."""
    return is_valid_model_dir(model_dir(size))
