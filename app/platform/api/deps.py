# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for platform (config) API handlers."""

from typing import Annotated

from fastapi import Depends

from app.platform.services.config import ConfigService


def get_config_service() -> type[ConfigService]:
    """Return the config service class used by API handlers."""
    return ConfigService


ConfigServiceDep = Annotated[type[ConfigService], Depends(get_config_service)]
