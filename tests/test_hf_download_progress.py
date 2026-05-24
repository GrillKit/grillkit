# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Hugging Face download progress mapping."""

from pathlib import Path

from app.shared.infrastructure.hf_download_progress import (
    copy_file_with_progress,
    hf_progress_tqdm_factory,
)


class TestHfProgressTqdmFactory:
    """Tests for hf_progress_tqdm_factory."""

    def test_maps_byte_ratio_to_percent_range(self) -> None:
        """Progress callback receives mapped percent from tqdm byte counts."""
        seen: list[int] = []
        progress_tqdm = hf_progress_tqdm_factory(
            seen.append,
            percent_min=10,
            percent_max=90,
        )
        bar = progress_tqdm(total=200)
        bar.update(100)
        assert seen[-1] == 50

    def test_uses_expected_bytes_when_total_unknown(self) -> None:
        """Progress uses expected_bytes when hub total is missing."""
        seen: list[int] = []
        progress_tqdm = hf_progress_tqdm_factory(
            seen.append,
            percent_min=10,
            percent_max=90,
            expected_bytes=100,
        )
        bar = progress_tqdm()
        bar.update(50)
        assert seen[-1] == 50

    def test_uses_min_when_no_total_and_no_expected_bytes(self) -> None:
        """Progress reports percent_min when size is completely unknown."""
        seen: list[int] = []
        progress_tqdm = hf_progress_tqdm_factory(
            seen.append,
            percent_min=7,
            percent_max=80,
        )
        progress_tqdm()
        assert seen[-1] == 7


class TestCopyFileWithProgress:
    """Tests for copy_file_with_progress."""

    def test_reports_progress_while_copying(self, tmp_path: Path) -> None:
        """Chunked copy maps bytes copied into the configured percent range."""
        source = tmp_path / "source.bin"
        destination = tmp_path / "nested" / "dest.bin"
        source.write_bytes(b"x" * 2048)
        seen: list[int] = []

        copy_file_with_progress(
            source,
            destination,
            seen.append,
            percent_min=20,
            percent_max=80,
            chunk_size=1024,
        )

        assert destination.read_bytes() == source.read_bytes()
        assert seen[0] >= 20
        assert seen[-1] == 80
        assert seen == sorted(seen)
