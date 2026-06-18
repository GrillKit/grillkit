# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for AI provider lifecycle helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.platform.services.ai_context import ai_provider_from_config


class TestAiProviderFromConfig:
    """Tests for ai_provider_from_config context manager."""

    @pytest.mark.asyncio
    async def test_yields_provider(self):
        """Context manager yields a configured AI provider."""
        mock_provider = MagicMock()
        mock_provider.close = AsyncMock()

        with patch(
            "app.platform.services.ai_context.ConfigService.create_provider_from_config",
            return_value=mock_provider,
        ):
            async with ai_provider_from_config() as provider:
                assert provider == mock_provider

    @pytest.mark.asyncio
    async def test_closes_provider_on_exit(self):
        """Provider is closed when exiting the context manager."""
        mock_provider = MagicMock()
        mock_provider.close = AsyncMock()

        with patch(
            "app.platform.services.ai_context.ConfigService.create_provider_from_config",
            return_value=mock_provider,
        ):
            async with ai_provider_from_config():
                pass

        mock_provider.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_closes_provider_on_exception(self):
        """Provider is closed even when an exception occurs inside the context."""
        mock_provider = MagicMock()
        mock_provider.close = AsyncMock()

        with patch(
            "app.platform.services.ai_context.ConfigService.create_provider_from_config",
            return_value=mock_provider,
        ):
            with pytest.raises(ValueError, match="boom"):
                async with ai_provider_from_config():
                    raise ValueError("boom")

        mock_provider.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_warning_when_close_fails(self):
        """Close errors are logged but not re-raised."""
        mock_provider = MagicMock()
        mock_provider.close = AsyncMock(side_effect=RuntimeError("close failed"))

        with (
            patch(
                "app.platform.services.ai_context.ConfigService.create_provider_from_config",
                return_value=mock_provider,
            ),
            patch(
                "app.platform.services.ai_context.logger"
            ) as mock_logger,
        ):
            async with ai_provider_from_config():
                pass

        mock_provider.close.assert_awaited_once()
        mock_logger.warning.assert_called_once()
        args = mock_logger.warning.call_args[0]
        assert "Failed to close AI provider" in args[0]
        assert "close failed" in str(args[1])

    @pytest.mark.asyncio
    async def test_raises_when_no_config(self):
        """ValueError propagates when no configuration exists."""
        with patch(
            "app.platform.services.ai_context.ConfigService.create_provider_from_config",
            side_effect=ValueError("No configuration found"),
        ):
            with pytest.raises(ValueError, match="No configuration found"):
                async with ai_provider_from_config():
                    pass  # pragma: no cover
