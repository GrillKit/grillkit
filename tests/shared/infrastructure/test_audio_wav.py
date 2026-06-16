# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for canonical WAV validation and decoding."""

import io
import wave

import numpy as np
import pytest

from app.ai.audio_probe import minimal_wav_bytes
from app.shared.infrastructure.audio_wav import (
    CANONICAL_AUDIO_SAMPLE_RATE_HZ,
    pcm16le_to_float32,
    validate_wav_bytes,
    wav_bytes_to_float32,
)


def _write_wav(
    *,
    channels: int = 1,
    sample_width: int = 2,
    sample_rate: int = CANONICAL_AUDIO_SAMPLE_RATE_HZ,
    frame_count: int = 1600,
) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


class TestPcm16LeToFloat32:
    """Tests for PCM conversion helper."""

    def test_empty_pcm_returns_empty_array(self) -> None:
        """Empty PCM yields an empty float32 array."""
        result = pcm16le_to_float32(b"")
        assert result.dtype == np.float32
        assert result.size == 0

    def test_silence_is_zero(self) -> None:
        """Silent PCM samples decode to zero."""
        result = pcm16le_to_float32(b"\x00\x00" * 4)
        assert result.tolist() == [0.0, 0.0, 0.0, 0.0]


class TestValidateWavBytes:
    """Tests for canonical WAV validation."""

    def test_accepts_minimal_probe_wav(self) -> None:
        """Probe WAV matches canonical requirements."""
        validate_wav_bytes(minimal_wav_bytes())

    def test_rejects_empty_payload(self) -> None:
        """Empty uploads are rejected."""
        with pytest.raises(ValueError, match="empty"):
            validate_wav_bytes(b"")

    def test_rejects_stereo(self) -> None:
        """Only mono WAV is accepted."""
        payload = _write_wav(channels=2)
        with pytest.raises(ValueError, match="mono"):
            validate_wav_bytes(payload)

    def test_rejects_non_16_bit(self) -> None:
        """Only 16-bit PCM is accepted."""
        payload = _write_wav(sample_width=1)
        with pytest.raises(ValueError, match="16-bit"):
            validate_wav_bytes(payload)

    def test_rejects_non_16khz(self) -> None:
        """Only 16 kHz sample rate is accepted."""
        payload = _write_wav(sample_rate=44100)
        with pytest.raises(ValueError, match="16000 Hz"):
            validate_wav_bytes(payload)

    def test_rejects_zero_frames(self) -> None:
        """WAV files without samples are rejected."""
        payload = _write_wav(frame_count=0)
        with pytest.raises(ValueError, match="no samples"):
            validate_wav_bytes(payload)


class TestWavBytesToFloat32:
    """Tests for validated WAV decoding."""

    def test_decodes_minimal_probe_wav(self) -> None:
        """Valid WAV decodes to float32 samples."""
        samples = wav_bytes_to_float32(minimal_wav_bytes(duration_sec=0.1))
        assert samples.dtype == np.float32
        assert samples.size > 0
        assert float(np.max(np.abs(samples))) == 0.0

    def test_invalid_wav_raises(self) -> None:
        """Invalid payloads fail before decoding."""
        with pytest.raises(ValueError, match="valid WAV"):
            wav_bytes_to_float32(b"not-a-wav")
