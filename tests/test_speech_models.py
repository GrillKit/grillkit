# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for speech model domain metadata."""

import pytest

from app.speech.domain.models import (
    SPEECH_MODEL_BY_SIZE,
    normalize_speech_model_size,
    speech_model_spec_for_size,
)


def test_all_sizes_have_specs():
    """Every supported size has metadata and a Hugging Face repo id."""
    for size in ("small", "medium", "large"):
        spec = speech_model_spec_for_size(size)
        assert spec.size == size
        assert spec.hf_repo_id.startswith("Systran/")


def test_normalize_speech_model_size():
    """Size codes are normalized to lowercase."""
    assert normalize_speech_model_size(" Medium ") == "medium"


def test_normalize_rejects_unknown_size():
    """Unknown sizes raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported speech model size"):
        normalize_speech_model_size("xl")


def test_specs_cover_expected_sizes():
    """Registry contains small, medium, and large entries."""
    assert set(SPEECH_MODEL_BY_SIZE) == {"small", "medium", "large"}
