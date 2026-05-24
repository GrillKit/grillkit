# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Map Hugging Face Hub tqdm progress to application download percent."""

from collections.abc import Callable
import io
from pathlib import Path
import shutil
from typing import Any

from tqdm.std import tqdm

_DEFAULT_COPY_CHUNK_BYTES = 1 << 20


def hf_progress_tqdm_factory(
    on_percent: Callable[[int], None],
    *,
    percent_min: int = 5,
    percent_max: int = 95,
    expected_bytes: int | None = None,
) -> Any:
    """Build a tqdm class that forwards byte progress to ``on_percent``.

    Hugging Face Hub passes ``tqdm_class`` into ``snapshot_download`` and
    ``hf_hub_download``. The returned class is instantiated by the hub with
    ``total`` and updated as bytes are received.

    Args:
        on_percent: Callback invoked with an integer percent in
            ``[percent_min, percent_max]``.
        percent_min: Percent mapped from zero bytes downloaded.
        percent_max: Percent mapped when the bar reaches its total.
        expected_bytes: Fallback total size when the hub does not know
            ``Content-Length`` yet (common for single-file downloads).

    Returns:
        A ``tqdm`` subclass suitable for Hugging Face ``tqdm_class=...``.
    """

    def emit_percent(bar: Any) -> None:
        total = bar.total
        if total is None or total <= 0:
            total = expected_bytes
        if total is None or total <= 0:
            on_percent(percent_min)
            return
        ratio = min(1.0, max(0.0, bar.n / total))
        span = percent_max - percent_min
        on_percent(percent_min + int(span * ratio))

    class HfDownloadProgressBar(tqdm):  # type: ignore[type-arg]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("file", io.StringIO())
            super().__init__(*args, **kwargs)
            emit_percent(self)

        def update(self, n: float | None = 1) -> bool | None:
            result = super().update(n)
            emit_percent(self)
            return result

        def refresh(self, *args: Any, **kwargs: Any) -> None:
            super().refresh(*args, **kwargs)
            emit_percent(self)

    return HfDownloadProgressBar


def copy_file_with_progress(
    source: Path,
    destination: Path,
    on_percent: Callable[[int], None],
    *,
    percent_min: int = 5,
    percent_max: int = 95,
    chunk_size: int = _DEFAULT_COPY_CHUNK_BYTES,
) -> None:
    """Copy a file in chunks while reporting mapped download percent.

    Args:
        source: Existing file to copy (for example a Hugging Face cache path).
        destination: Target path to create or overwrite.
        on_percent: Callback invoked with percent in ``[percent_min, percent_max]``.
        percent_min: Percent when no bytes have been copied yet.
        percent_max: Percent when the full file has been copied.
        chunk_size: Read size per progress update.
    """
    total_bytes = source.stat().st_size
    if total_bytes <= 0:
        on_percent(percent_max)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    copied = 0
    span = percent_max - percent_min
    with source.open("rb") as src, destination.open("wb") as dst:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            ratio = min(1.0, copied / total_bytes)
            on_percent(percent_min + int(span * ratio))
