# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Hugging Face Hub download settings for GrillKit."""

import os

from app.paths import DATA_DIR

_CONFIGURED = False

_HTTP_DOWNLOAD_CHUNK_SIZE = 512 * 1024
_HF_HOME = DATA_DIR / ".cache" / "huggingface"


def configure_hf_hub() -> None:
    """Prefer HTTP Hub downloads over Xet for Whisper and Piper models.

    Some networks stall Xet transfers at 0 bytes while HTTP downloads work.
    ``HF_HUB_DISABLE_XET`` alone is ignored when ``hf_xet`` is installed, so
    Xet is disabled explicitly. Smaller HTTP chunks improve progress reporting.

    Hub cache is stored under ``data/.cache/huggingface`` so downloads work
    in Docker when the process has no writable home directory.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    _HF_HOME.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(_HF_HOME))

    from huggingface_hub import constants as hf_constants
    from huggingface_hub import file_download as hf_file_download

    hf_constants.DOWNLOAD_CHUNK_SIZE = _HTTP_DOWNLOAD_CHUNK_SIZE
    hf_file_download.is_xet_available = lambda: False  # type: ignore[attr-defined]

    _CONFIGURED = True
