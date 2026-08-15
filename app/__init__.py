# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""GrillKit application package."""

from importlib.metadata import PackageNotFoundError, version
from app.shared.infrastructure.hf_hub_runtime import configure_hf_hub

try:
    __version__ = version("grillkit")
except PackageNotFoundError:
    __version__ = "2026.8.9"


configure_hf_hub()
