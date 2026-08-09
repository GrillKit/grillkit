# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""On-disk paths and validation for installed Piper voices."""

from pathlib import Path

from app.shared.paths import PIPER_VOICES_ROOT
from app.shared.tts_voices import normalize_tts_voice_id


def voice_dir(voice_id: str) -> Path:
    """Return the installation directory for a Piper voice id."""
    code = normalize_tts_voice_id(voice_id)
    return PIPER_VOICES_ROOT / code


def is_valid_voice_dir(path: Path, voice_id: str) -> bool:
    """Return whether ``path`` contains a Piper voice model pair.

    Args:
        path: Directory that may hold ``<voice_id>.onnx`` and ``.onnx.json``.
        voice_id: Piper voice identifier (file name prefix, not ``path.name``).
    """
    if not path.is_dir():
        return False
    code = normalize_tts_voice_id(voice_id)
    return (path / f"{code}.onnx").is_file() and (path / f"{code}.onnx.json").is_file()


def is_voice_installed(voice_id: str) -> bool:
    """Return whether a valid Piper voice is present for the id."""
    return is_valid_voice_dir(voice_dir(voice_id), voice_id)
