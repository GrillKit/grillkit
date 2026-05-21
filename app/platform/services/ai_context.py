# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""AI provider lifecycle helpers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from app.ai.base import AIProvider
from app.platform.services.config import ConfigService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ai_provider_from_config() -> AsyncIterator[AIProvider]:
    """Yield a configured AI provider and ensure it is closed.

    Yields:
        Configured AIProvider instance.

    Raises:
        ValueError: If provider configuration is missing.
    """
    provider = ConfigService.create_provider_from_config()
    try:
        yield provider
    finally:
        try:
            await provider.close()
        except Exception as e:
            logger.warning("Failed to close AI provider: %s", e)
