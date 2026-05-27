# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Whisper speech model metadata and normalization for speech services."""

from dataclasses import dataclass
from typing import Final, Literal

SpeechModelSize = Literal["small", "medium", "large"]
DEFAULT_SPEECH_MODEL_SIZE: Final[SpeechModelSize] = "small"
SPEECH_MODEL_SIZES: Final[tuple[SpeechModelSize, ...]] = (
    "small",
    "medium",
    "large",
)


@dataclass(frozen=True)
class SpeechModelSpec:
    """Published faster-whisper model for one size tier.

    Attributes:
        size: Model size identifier.
        display_name: Human-readable label for UI.
        hf_repo_id: Hugging Face repository id for snapshot download.
        approx_download_mb: Approximate download size for trade-off hints.
        ram_hint: Suggested RAM for running the model.
        speed_hint: Relative speed expectation on CPU.
        quality_hint: Relative transcription quality.
    """

    size: SpeechModelSize
    display_name: str
    hf_repo_id: str
    approx_download_mb: int
    ram_hint: str
    speed_hint: str
    quality_hint: str


SPEECH_MODEL_BY_SIZE: Final[dict[SpeechModelSize, SpeechModelSpec]] = {
    "small": SpeechModelSpec(
        size="small",
        display_name="Whisper small",
        hf_repo_id="Systran/faster-whisper-small",
        approx_download_mb=500,
        ram_hint="~1 GB",
        speed_hint="Fastest on CPU",
        quality_hint="Good for short answers",
    ),
    "medium": SpeechModelSpec(
        size="medium",
        display_name="Whisper medium",
        hf_repo_id="Systran/faster-whisper-medium",
        approx_download_mb=1500,
        ram_hint="~2–3 GB",
        speed_hint="Slower on CPU",
        quality_hint="Better accuracy and noise handling",
    ),
    "large": SpeechModelSpec(
        size="large",
        display_name="Whisper large",
        hf_repo_id="Systran/faster-whisper-large-v3",
        approx_download_mb=3000,
        ram_hint="~4+ GB",
        speed_hint="Slowest; best with GPU",
        quality_hint="Highest accuracy",
    ),
}


def normalize_speech_model_size(size: str) -> SpeechModelSize:
    """Return a supported speech model size or raise ``ValueError``.

    Args:
        size: Requested size (e.g. ``small``, ``medium``).

    Returns:
        Normalized size present in ``SPEECH_MODEL_BY_SIZE``.

    Raises:
        ValueError: If the size is not supported.
    """
    code = size.strip().lower()
    if code not in SPEECH_MODEL_BY_SIZE:
        supported = ", ".join(SPEECH_MODEL_SIZES)
        raise ValueError(
            f"Unsupported speech model size '{size}'. Choose one of: {supported}"
        )
    return code


def speech_model_spec_for_size(size: str) -> SpeechModelSpec:
    """Return speech model metadata for a supported size.

    Args:
        size: Speech model size identifier.

    Returns:
        Model metadata for the size.

    Raises:
        ValueError: If the size is not supported.
    """
    code = normalize_speech_model_size(size)
    return SPEECH_MODEL_BY_SIZE[code]
