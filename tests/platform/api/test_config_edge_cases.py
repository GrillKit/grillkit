# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Config edge cases: locale change, delete config preserves sessions, invalid URL."""

from unittest.mock import patch

from app.ai.llm_models import LLMModelEntry
from app.platform.services.config import AppConfig


class TestConfigEdgeCases:
    """Tests for configuration edge cases."""

    def _catalog_entry(self):
        from app.ai.llm_models import LLMModelEntry
        return LLMModelEntry(
            id="cloud",
            display_name="Cloud",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.openai.com",
            api_key_required=True,
            api_key="stored-secret",
        )

    def test_locale_change_saved(self, client, isolated_db):
        """Locale change written to config and used in new sessions."""
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry(),
            ),
            patch(
                "app.platform.services.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry(),
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.save_config"
            ) as mock_save,
        ):
            response = client.post(
                "/config",
                data={
                    "llm_preset_id": "cloud",
                    "api_key": "test-key",
                    "timeout": "60",
                    "locale": "ru",
                },
            )
        assert response.status_code == 200
        saved = mock_save.call_args[0][0]
        assert saved.locale == "ru"

    def test_config_delete_keeps_sessions(self, client, isolated_db):
        """Deleting config does not affect existing interviews."""
        from app.shared.infrastructure.models import Interview
        from tests.helpers.interview_seed import persist_interview_with_answers
        from tests.helpers.selection import minimal_selection_spec

        interview_id = persist_interview_with_answers(
            Interview(
                id="cfg-delete-1",
                locale="en",
                selection_spec=minimal_selection_spec(),
                status="active",
            ),
            [],
            question_count=5,
        )

        with patch(
            "app.platform.services.config.ConfigService.delete_config"
        ) as mock_delete:
            client.delete("/config")
            mock_delete.assert_called_once()

        # Existing session still reachable
        from app.interview.repositories.uow import InterviewUnitOfWork
        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview is not None
            assert interview.status == "active"

    def test_add_model_rejects_invalid_url(self, client, isolated_db):
        """Adding model with unreachable URL fails validation."""
        with (
            patch(
                "app.platform.services.config.ConfigService.test_catalog_model",
                return_value=(False, "Connection refused"),
            ),
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
        ):
            response = client.post(
                "/config/llm-models",
                data={
                    "display_name": "Broken",
                    "base_url": "http://invalid-url-test",
                    "model": "none",
                    "api_key": "",
                    "api_key_required": "",
                },
            )
        assert response.status_code == 200
        text = response.text
        assert "error" in text.lower() or "refused" in text.lower()

    def test_add_model_with_accepts_audio_input_flag(self, client, isolated_db):
        """S12.2: Adding model with accepts_audio_input=true stores the flag."""
        added_entry = LLMModelEntry(
            id="audio-model-id",
            display_name="Audio Model",
            provider_type="openai-compatible",
            model="gpt-4o-audio",
            base_url="https://api.openai.com/v1",
            api_key_required=True,
            api_key="test-key",
            accepts_audio_input=True,
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.test_catalog_model",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=None,
            ),
            patch(
                "app.platform.services.llm_catalog.LLMCatalogService.add_user_model",
                return_value=added_entry,
            ) as mock_add,
        ):
            response = client.post(
                "/config/llm-models",
                data={
                    "display_name": "Audio Model",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4o-audio",
                    "api_key": "test-key",
                    "api_key_required": "on",
                    "accepts_audio_input": "on",
                },
            )
        assert response.status_code == 200
        mock_add.assert_called_once()
        call_args = mock_add.call_args
        payload = call_args[0][0] if call_args[0] else call_args[1]
        assert payload.accepts_audio_input is True

    def test_config_save_without_api_key_when_not_required(self, client, isolated_db):
        """S12.5: Save config with empty api_key when api_key_required=false works."""
        ollama_entry = LLMModelEntry(
            id="local",
            display_name="Ollama Local",
            provider_type="openai-compatible",
            model="llama3",
            base_url="http://localhost:11434/v1",
            api_key_required=False,
            api_key=None,
        )
        with (
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="local",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=ollama_entry,
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.save_config"
            ) as mock_save,
        ):
            response = client.post(
                "/config",
                data={
                    "llm_preset_id": "local",
                    "api_key": "",  # empty
                    "timeout": "60",
                    "locale": "en",
                },
            )
        assert response.status_code == 200
        saved = mock_save.call_args[0][0]
        assert saved.api_key is None or saved.api_key == ""

    def test_speech_model_size_change_stored(self, client, isolated_db):
        """S12.4: Changing speech_model_size is persisted in config."""
        existing = AppConfig(
            provider_type="openai-compatible",
            base_url="https://api.openai.com",
            model="gpt-4",
            api_key="stored-secret",
            llm_preset_id="cloud",
            speech_model_size="small",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=existing,
            ),
            patch(
                "app.platform.services.config_form.normalize_model_id",
                return_value="cloud",
            ),
            patch(
                "app.platform.api.config.LLMCatalogService.get_model",
                return_value=self._catalog_entry(),
            ),
            patch(
                "app.platform.services.config.ConfigService.test_connection",
                return_value=(True, "OK"),
            ),
            patch(
                "app.platform.services.config.ConfigService.save_config"
            ) as mock_save,
        ):
            response = client.post(
                "/config",
                data={
                    "llm_preset_id": "cloud",
                    "api_key": "",
                    "timeout": "60",
                    "locale": "en",
                    "speech_model_size": "medium",
                    "question_voice_enabled": "",
                },
            )
        assert response.status_code == 200
        saved = mock_save.call_args[0][0]
        assert saved.speech_model_size == "medium"
