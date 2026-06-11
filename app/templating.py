# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared Jinja2 templates and static asset helpers."""

from fastapi.templating import Jinja2Templates

from app.shared.paths import STATIC_DIR, TEMPLATES_DIR

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def static_version(relative_path: str) -> str:
    """Return a cache-busting version token for a file under ``static/``.

    Args:
        relative_path: Path relative to the static directory (e.g. ``css/styles.css``).

    Returns:
        ``mtime`` as an integer string, or ``0`` if the file is missing.
    """
    path = STATIC_DIR / relative_path
    if path.is_file():
        return str(int(path.stat().st_mtime))
    return "0"


templates.env.globals["static_version"] = static_version
