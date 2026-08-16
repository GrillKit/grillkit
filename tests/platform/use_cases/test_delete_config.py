# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for DeleteConfigUseCase."""

from unittest.mock import MagicMock, patch

from app.platform.domain.config import ConfigService
from app.platform.use_cases.delete_config import DeleteConfigUseCase


class TestDeleteConfigUseCase:
    """Tests for the delete-config orchestration."""

    def test_deletes_config_and_unloads_speech(self):
        """Delete removes the persisted config and unloads speech runtimes."""
        coordinator = MagicMock()
        use_case = DeleteConfigUseCase(ConfigService, coordinator)

        with patch.object(ConfigService, "delete_config") as mock_delete:
            use_case.execute()

        mock_delete.assert_called_once_with()
        coordinator.unload_all.assert_called_once_with()
