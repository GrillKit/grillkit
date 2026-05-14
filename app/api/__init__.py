# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""API endpoint modules.

This package contains all API endpoint modules for the GrillKit application.
"""

from .config import router as config_router
from .root import router as root_router

__all__ = ["config_router", "root_router"]
