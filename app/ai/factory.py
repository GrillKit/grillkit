# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""AI provider factory.

This module provides factory functions for creating AI provider instances
from user configuration.
"""

from app.ai.base import AIProvider
from app.ai.openai_compatible import OpenAICompatibleProvider


class ProviderFactory:
    """Factory for creating AI provider instances from user configuration."""

    @classmethod
    def from_config(
        cls,
        base_url: str,
        model: str,
        api_key: str | None = None,
        api_type: str = "openai-compatible",
        timeout: float = 60.0,
        **kwargs: object,
    ) -> AIProvider:
        """Create a provider from user-provided configuration.

        Args:
            base_url: API endpoint URL (e.g., https://api.openai.com/v1).
            model: Model name to use.
            api_key: API key (optional for local providers).
            api_type: API type - currently only "openai-compatible" is supported.
            timeout: Request timeout in seconds.
            **kwargs: Additional options.

        Returns:
            Configured AIProvider instance.

        Raises:
            ValueError: If api_type is not supported.
        """
        if api_type == "openai-compatible":
            return OpenAICompatibleProvider(
                model=model,
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
            )

        raise ValueError(f"Unsupported API type: {api_type}")
