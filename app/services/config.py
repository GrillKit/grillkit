# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration service module.

This module provides service layer for managing AI provider configuration
stored in data/config.json.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..ai.factory import ProviderFactory

CONFIG_DIR = Path(__file__).parent.parent.parent / "data"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class ProviderConfig:
    """AI provider configuration.

    Attributes:
        provider_type: Type of AI provider (e.g., "openai-compatible").
        base_url: API endpoint URL.
        model: Model name to use.
        api_key: API key for authentication (optional for local providers).
        timeout: Request timeout in seconds.
    """

    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0

    def to_dict(self, mask_secret: bool = False) -> dict[str, Any]:
        """Convert to dictionary.

        Args:
            mask_secret: If True, mask api_key as "***".

        Returns:
            Dictionary representation of the configuration.
        """
        return {
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": "***" if mask_secret and self.api_key else self.api_key,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with configuration values.

        Returns:
            ProviderConfig instance.
        """
        return cls(
            provider_type=data.get("provider_type", "openai-compatible"),
            base_url=data.get("base_url", ""),
            model=data.get("model", ""),
            api_key=data.get("api_key"),
            timeout=data.get("timeout", 60.0),
        )


class ConfigService:
    """Service for managing provider configuration."""

    @staticmethod
    def get_config() -> ProviderConfig | None:
        """Load configuration from file.

        Returns:
            ProviderConfig if file exists, None otherwise.
        """
        if not CONFIG_PATH.exists():
            return None
        data = json.loads(CONFIG_PATH.read_text())
        return ProviderConfig.from_dict(data)

    @staticmethod
    def save_config(config: ProviderConfig) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config.to_dict(), indent=2))

    @staticmethod
    def delete_config() -> None:
        """Remove configuration file."""
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()

    @staticmethod
    async def test_connection(config: ProviderConfig) -> tuple[bool, str]:
        """Test provider connection without saving.

        Args:
            config: Configuration to test.

        Returns:
            Tuple of (success: bool, message: str).
        """
        try:
            provider = ProviderFactory.from_config(
                api_type=config.provider_type,
                base_url=config.base_url,
                model=config.model,
                api_key=config.api_key,
                timeout=config.timeout,
            )
            is_valid = await provider.validate()
            if is_valid:
                return True, "Connection successful"
            return False, "Invalid API key or unreachable endpoint"
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {e}"

    @staticmethod
    def create_provider_from_config():
        """Create AI provider from saved configuration.

        Returns:
            Configured AI provider instance.

        Raises:
            ValueError: If no configuration exists.
        """
        config = ConfigService.get_config()
        if not config:
            raise ValueError("No configuration found")
        return ProviderFactory.from_config(
            api_type=config.provider_type,
            base_url=config.base_url,
            model=config.model,
            api_key=config.api_key,
            timeout=config.timeout,
        )
