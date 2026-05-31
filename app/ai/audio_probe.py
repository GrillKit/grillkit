# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Minimal WAV payloads for audio capability probes."""

import io
import wave

from app.shared.infrastructure.audio_wav import CANONICAL_AUDIO_SAMPLE_RATE_HZ

__all__ = ["minimal_wav_bytes"]


def minimal_wav_bytes(
    *,
    sample_rate: int = CANONICAL_AUDIO_SAMPLE_RATE_HZ,
    duration_sec: float = 0.1,
) -> bytes:
    """Build a short silent mono PCM WAV for connection testing.

    Args:
        sample_rate: Sample rate in Hz.
        duration_sec: Duration of silence in seconds.

    Returns:
        WAV file bytes suitable for provider audio probes.
    """
    frame_count = max(1, int(sample_rate * duration_sec))
    pcm = b"\x00\x00" * frame_count
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()
