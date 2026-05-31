# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the LLM model catalog."""

import json

import pytest

from app.ai.llm_models import (
    CUSTOM_PRESET_ID,
    normalize_model_id,
    validate_new_model_id,
)
from app.platform.schemas import NewLLMModel
from app.platform.services.llm_catalog import LLMCatalogService


@pytest.fixture
def llm_catalog_path(tmp_path, monkeypatch):
    """Point catalog path at a temporary JSON file."""
    catalog_path = tmp_path / "llm_models.json"
    monkeypatch.setattr(
        "app.platform.services.llm_catalog.LLM_MODELS_PATH", catalog_path
    )
    yield catalog_path


class TestLLMCatalog:
    """Tests for catalog loading and model persistence."""

    def test_load_catalog_empty_when_file_missing(self, llm_catalog_path):
        """Missing catalog file yields an empty catalog."""
        catalog = LLMCatalogService.load_catalog()
        assert catalog.selected_id is None
        assert catalog.models == {}

    def test_add_user_model_persists_accepts_audio_input(self, llm_catalog_path):
        """Audio capability flag round-trips through llm_models.json."""
        entry = LLMCatalogService.add_user_model(
            NewLLMModel(
                model_id="audio",
                display_name="Audio API",
                base_url="https://api.example.com/v1",
                model="gpt-4o-audio",
                accepts_audio_input=True,
            )
        )
        assert entry.accepts_audio_input is True
        saved = json.loads(llm_catalog_path.read_text())
        assert saved["models"]["audio"]["accepts_audio_input"] is True

    def test_add_user_model_persists_api_key(self, llm_catalog_path):
        """Models can store an API key in llm_models.json."""
        entry = LLMCatalogService.add_user_model(
            NewLLMModel(
                model_id="cloud",
                display_name="Cloud API",
                base_url="https://api.example.com/v1",
                model="gpt-4",
                api_key="secret-key",
            )
        )
        assert entry.api_key == "secret-key"
        saved = json.loads(llm_catalog_path.read_text())
        assert saved["models"]["cloud"]["api_key"] == "secret-key"
        assert saved["models"]["cloud"]["base_url"] == "https://api.example.com/v1"

    def test_add_user_model_sets_selected(self, llm_catalog_path):
        """Adding a model selects it in llm_models.json."""
        LLMCatalogService.add_user_model(
            NewLLMModel(
                model_id="my-work",
                display_name="Work API",
                base_url="http://192.168.1.10:11434/v1",
                model="deepseek-coder-v2:16b",
            )
        )
        saved = json.loads(llm_catalog_path.read_text())
        assert saved["selected"] == "my-work"

    def test_add_user_model_rejects_duplicate_id(self, llm_catalog_path):
        """Duplicate model ids are rejected."""
        payload = NewLLMModel(
            model_id="cloud",
            display_name="Cloud",
            base_url="https://api.example.com/v1",
            model="gpt-4",
        )
        LLMCatalogService.add_user_model(payload)
        with pytest.raises(ValueError, match="already exists"):
            LLMCatalogService.add_user_model(payload)

    def test_normalize_model_id_rejects_custom(self, llm_catalog_path):
        """Custom sentinel is not a valid catalog selection."""
        catalog = LLMCatalogService.load_catalog()
        with pytest.raises(ValueError, match="Interview model is required"):
            normalize_model_id(CUSTOM_PRESET_ID, catalog)

    def test_normalize_model_id_rejects_unknown(self, llm_catalog_path):
        """Unknown ids raise ValueError."""
        catalog = LLMCatalogService.load_catalog()
        with pytest.raises(ValueError, match="Unsupported LLM model"):
            normalize_model_id("missing", catalog)

    def test_get_model_strips_trailing_slash_from_base_url(self, llm_catalog_path):
        """Trailing slashes on base_url are normalized on read."""
        llm_catalog_path.write_text(
            json.dumps(
                {
                    "selected": "local",
                    "models": {
                        "local": {
                            "display_name": "Local",
                            "provider_type": "openai-compatible",
                            "model": "gpt-4",
                            "base_url": "http://localhost:11434/v1/",
                            "api_key_required": False,
                        }
                    },
                }
            )
        )
        entry = LLMCatalogService.get_model("local")
        assert entry is not None
        assert entry.base_url == "http://localhost:11434/v1"


class TestLLMModelHelpers:
    """Tests for id validation."""

    def test_validate_new_model_id_rejects_custom_sentinel(self):
        """Reserved custom sentinel cannot become a catalog id."""
        with pytest.raises(ValueError, match="reserved"):
            validate_new_model_id(CUSTOM_PRESET_ID)
