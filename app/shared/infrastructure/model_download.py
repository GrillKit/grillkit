# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for staged on-disk model downloads."""

from pathlib import Path
import shutil


def prepare_staging_dir(root: Path, staging_name: str) -> Path:
    """Create a clean staging directory under ``root``.

    Args:
        root: Parent directory for installed artifacts.
        staging_name: Staging folder name (e.g. ``.staging-tiny``).

    Returns:
        Path to the empty staging directory.
    """
    staging_dir = root / staging_name
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir


def promote_staging_dir(staging_dir: Path, target_dir: Path) -> None:
    """Replace ``target_dir`` with the contents of ``staging_dir``.

    Args:
        staging_dir: Temporary download directory.
        target_dir: Final installation path.
    """
    if target_dir.exists():
        shutil.rmtree(target_dir)
    staging_dir.rename(target_dir)


def cleanup_staging_dir(staging_dir: Path) -> None:
    """Remove a staging directory when it still exists.

    Args:
        staging_dir: Temporary download directory.
    """
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
