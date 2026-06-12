# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared artifact status resolution."""

from app.shared.infrastructure.artifact_download import ArtifactDownloadService
from app.shared.infrastructure.artifact_status import ArtifactStatusBuilder


class _StubDownloadService(ArtifactDownloadService):
    """Minimal download service for status builder tests."""


def test_build_reports_missing_when_not_installed():
    """Missing artifacts return the missing message."""
    built = ArtifactStatusBuilder.build(
        key="voice-a",
        service=_StubDownloadService,
        is_installed=lambda: False,
        is_loaded=lambda: False,
        load_error=lambda: None,
        downloading_message="Downloading…",
        missing_message="Not installed.",
        ready_loaded_message="Ready.",
        ready_loading_message="Loading…",
        ready_load_failed_message=lambda err: f"Failed: {err}",
    )
    assert built.state == "missing"
    assert built.message == "Not installed."


def test_build_reports_downloading():
    """Active downloads surface downloading state and percent."""
    _StubDownloadService._active_key = "voice-a"
    _StubDownloadService._percent = 55
    try:
        built = ArtifactStatusBuilder.build(
            key="voice-a",
            service=_StubDownloadService,
            is_installed=lambda: False,
            is_loaded=lambda: False,
            load_error=lambda: None,
            downloading_message="Downloading…",
            missing_message="Not installed.",
            ready_loaded_message="Ready.",
            ready_loading_message="Loading…",
            ready_load_failed_message=lambda err: f"Failed: {err}",
        )
        assert built.state == "downloading"
        assert built.percent == 55
    finally:
        _StubDownloadService.reset_download_state()
