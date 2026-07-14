# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Validate and decode canonical WAV audio for speech and interview flows."""

import io
import struct
import wave

import numpy as np
import numpy.typing as npt

CANONICAL_AUDIO_SAMPLE_RATE_HZ = 16000
CANONICAL_AUDIO_SAMPLE_WIDTH_BYTES = 2
CANONICAL_AUDIO_CHANNELS = 1


def pcm16le_to_float32(pcm: bytes) -> npt.NDArray[np.float32]:
    """Convert 16-bit signed little-endian mono PCM to normalized float32.

    Args:
        pcm: Raw PCM samples.

    Returns:
        Mono float32 samples in ``[-1.0, 1.0]``.
    """
    if not pcm:
        return np.array([], dtype=np.float32)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def validate_wav_bytes(wav_bytes: bytes) -> None:
    """Validate canonical WAV format for audio answers and transcription.

    Args:
        wav_bytes: Uploaded or recorded WAV payload.

    Raises:
        ValueError: If the payload is missing, invalid, or not canonical PCM WAV.
    """
    if not wav_bytes:
        raise ValueError("Audio payload is empty")

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            compression = wav_file.getcomptype()
    except (wave.Error, struct.error, EOFError) as exc:
        raise ValueError("Audio must be a valid WAV file") from exc

    if compression != "NONE":
        raise ValueError("Audio must be uncompressed PCM WAV")
    if channels != CANONICAL_AUDIO_CHANNELS:
        raise ValueError("Audio must be mono WAV")
    if sample_width != CANONICAL_AUDIO_SAMPLE_WIDTH_BYTES:
        raise ValueError("Audio must be 16-bit PCM WAV")
    if sample_rate != CANONICAL_AUDIO_SAMPLE_RATE_HZ:
        raise ValueError(
            f"Audio must use {CANONICAL_AUDIO_SAMPLE_RATE_HZ} Hz sample rate"
        )
    if frame_count <= 0:
        raise ValueError("Audio WAV contains no samples")


def wav_bytes_to_float32(wav_bytes: bytes) -> npt.NDArray[np.float32]:
    """Validate and decode canonical WAV bytes for Whisper transcription.

    Args:
        wav_bytes: Canonical mono 16 kHz PCM WAV payload.

    Returns:
        Mono float32 samples normalized to ``[-1.0, 1.0]``.

    Raises:
        ValueError: If the payload fails :func:`validate_wav_bytes`.
    """
    validate_wav_bytes(wav_bytes)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        pcm = wav_file.readframes(wav_file.getnframes())
    return pcm16le_to_float32(pcm)
