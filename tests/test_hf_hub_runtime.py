# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Hugging Face Hub runtime configuration."""

import os

from huggingface_hub import constants as hf_constants
from huggingface_hub import file_download as hf_file_download

from app.shared.infrastructure.hf_hub_runtime import configure_hf_hub


class TestConfigureHfHub:
    """Tests for configure_hf_hub."""

    def test_disables_xet_and_sets_chunk_size(self, monkeypatch) -> None:
        """HTTP downloads are forced and chunk size is reduced for progress updates."""
        monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)
        import app.shared.infrastructure.hf_hub_runtime as runtime_module

        monkeypatch.setattr(runtime_module, "_CONFIGURED", False)
        configure_hf_hub()
        assert os.environ.get("HF_HUB_DISABLE_XET") == "1"
        assert hf_file_download.is_xet_available() is False  # type: ignore[attr-defined]
        assert hf_constants.DOWNLOAD_CHUNK_SIZE == 512 * 1024

    def test_is_idempotent(self) -> None:
        """Second call does not change Hub settings."""
        configure_hf_hub()
        chunk_size = hf_constants.DOWNLOAD_CHUNK_SIZE
        configure_hf_hub()
        assert chunk_size == hf_constants.DOWNLOAD_CHUNK_SIZE
