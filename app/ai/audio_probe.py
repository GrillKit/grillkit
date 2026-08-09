# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Minimal WAV payloads for audio capability probes."""

import io
import math
import struct
import wave

from app.shared.infrastructure.audio_wav import CANONICAL_AUDIO_SAMPLE_RATE_HZ

__all__ = ["minimal_wav_bytes"]


def minimal_wav_bytes(
    *,
    sample_rate: int = CANONICAL_AUDIO_SAMPLE_RATE_HZ,
    duration_sec: float = 0.5,
    tone_freq_hz: float = 440.0,
) -> bytes:
    """Build a short mono PCM WAV beep for connection testing.

    A pure-silence clip is rejected by most multimodal audio models (they
    require audible speech), so the probe sends a short audible tone instead.

    Args:
        sample_rate: Sample rate in Hz.
        duration_sec: Duration of the tone in seconds.
        tone_freq_hz: Frequency of the probe tone in Hz.

    Returns:
        WAV file bytes suitable for provider audio probes.
    """
    frame_count = max(1, int(sample_rate * duration_sec))
    amplitude = 0.2  # moderate volume, well below clipping
    pcm = bytearray()
    for i in range(frame_count):
        sample = amplitude * math.sin(2 * math.pi * tone_freq_hz * i / sample_rate)
        pcm += struct.pack("<h", int(sample * 32767))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm))
    return buffer.getvalue()
