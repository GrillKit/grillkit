# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for LLM model catalog types."""

import pytest

from app.ai.llm_models import (
    CUSTOM_PRESET_ID,
    LLMCatalog,
    LLMModelEntry,
    generate_model_id,
    normalize_model_id,
    slugify_model_id,
)


class TestLLMModelEntry:
    """Tests for LLMModelEntry dataclass."""

    def test_creation_with_required_fields(self):
        """Entry can be created with all required fields."""
        entry = LLMModelEntry(
            id="gpt-4",
            display_name="GPT-4",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
            api_key_required=True,
        )
        assert entry.id == "gpt-4"
        assert entry.display_name == "GPT-4"
        assert entry.provider_type == "openai-compatible"
        assert entry.model == "gpt-4"
        assert entry.base_url == "https://api.openai.com/v1"
        assert entry.api_key_required is True
        assert entry.api_key is None
        assert entry.accepts_audio_input is False

    def test_creation_with_optional_fields(self):
        """Optional fields can be set explicitly."""
        entry = LLMModelEntry(
            id="custom-model",
            display_name="Custom",
            provider_type="openai-compatible",
            model="custom",
            base_url="http://localhost:11434",
            api_key_required=False,
            api_key="secret",
            accepts_audio_input=True,
        )
        assert entry.api_key == "secret"
        assert entry.accepts_audio_input is True

    def test_is_frozen(self):
        """Entry is immutable after creation."""
        entry = LLMModelEntry(
            id="x",
            display_name="X",
            provider_type="openai-compatible",
            model="x",
            base_url="http://localhost",
            api_key_required=False,
        )
        with pytest.raises(AttributeError):
            entry.display_name = "Y"


class TestLLMCatalog:
    """Tests for LLMCatalog dataclass."""

    def test_creation_with_models(self):
        """Catalog can be created with a full model map."""
        entry = LLMModelEntry(
            id="gpt-4",
            display_name="GPT-4",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
            api_key_required=True,
        )
        catalog = LLMCatalog(
            selected_id="gpt-4",
            models={"gpt-4": entry},
        )
        assert catalog.selected_id == "gpt-4"
        assert "gpt-4" in catalog.models

    def test_creation_without_selection(self):
        """Catalog can have None selected_id."""
        catalog = LLMCatalog(
            selected_id=None,
            models={},
        )
        assert catalog.selected_id is None
        assert catalog.models == {}

    def test_is_frozen(self):
        """Catalog is immutable after creation."""
        catalog = LLMCatalog(selected_id=None, models={})
        with pytest.raises(AttributeError):
            catalog.selected_id = "x"


class TestNormalizeModelId:
    """Tests for normalize_model_id."""

    def test_returns_valid_id(self):
        """Returns the id when it exists in catalog."""
        entry = LLMModelEntry(
            id="gpt-4",
            display_name="GPT-4",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
            api_key_required=True,
        )
        catalog = LLMCatalog(
            selected_id="gpt-4",
            models={"gpt-4": entry},
        )
        assert normalize_model_id("gpt-4", catalog) == "gpt-4"

    def test_strips_whitespace(self):
        """Strips whitespace from the input id."""
        entry = LLMModelEntry(
            id="gpt-4",
            display_name="GPT-4",
            provider_type="openai-compatible",
            model="gpt-4",
            base_url="https://api.openai.com/v1",
            api_key_required=True,
        )
        catalog = LLMCatalog(
            selected_id="gpt-4",
            models={"gpt-4": entry},
        )
        assert normalize_model_id("  gpt-4  ", catalog) == "gpt-4"

    def test_rejects_empty_string(self):
        """Raises ValueError for empty string."""
        catalog = LLMCatalog(selected_id=None, models={})
        with pytest.raises(ValueError, match="Interview model is required"):
            normalize_model_id("", catalog)

    def test_rejects_custom_preset_id(self):
        """Raises ValueError when id matches CUSTOM_PRESET_ID."""
        catalog = LLMCatalog(selected_id=None, models={})
        with pytest.raises(ValueError, match="Interview model is required"):
            normalize_model_id(CUSTOM_PRESET_ID, catalog)

    def test_rejects_unknown_id(self):
        """Raises ValueError for unknown model ids."""
        catalog = LLMCatalog(
            selected_id=None,
            models={},
        )
        with pytest.raises(ValueError, match="Unsupported LLM model: unknown"):
            normalize_model_id("unknown", catalog)

    def test_rejects_whitespace_only(self):
        """Raises ValueError for whitespace-only input."""
        catalog = LLMCatalog(selected_id=None, models={})
        with pytest.raises(ValueError, match="Interview model is required"):
            normalize_model_id("   ", catalog)


class TestSlugifyModelId:
    """Tests for slugify_model_id."""

    def test_lowercases_text(self):
        """Result is all lowercase."""
        assert slugify_model_id("GPT-4 Turbo") == "gpt-4-turbo"

    def test_replaces_spaces_with_hyphens(self):
        """Spaces become single hyphens."""
        assert slugify_model_id("my model name") == "my-model-name"

    def test_replaces_special_chars(self):
        """Special characters become hyphens."""
        assert slugify_model_id("model@v1.5") == "model-v1-5"

    def test_collapses_multiple_special_chars(self):
        """Runs of non-alphanumeric chars collapse to one hyphen."""
        assert slugify_model_id("a!!!b") == "a-b"

    def test_strips_leading_trailing_hyphens(self):
        """Leading and trailing hyphens are removed."""
        assert slugify_model_id("!!!test!!!") == "test"

    def test_empty_result_for_no_usable_chars(self):
        """Returns empty string when input has no alphanumeric chars."""
        assert slugify_model_id("!!!") == ""

    def test_strips_input_whitespace(self):
        """Input whitespace is stripped before processing."""
        assert slugify_model_id("  Model Name  ") == "model-name"


class TestGenerateModelId:
    """Tests for generate_model_id."""

    def test_generates_slug_from_display_name(self):
        """Generates a slug from display name."""
        result = generate_model_id("My New Model", [])
        assert result == "my-new-model"

    def test_returns_unique_id(self):
        """Appends a suffix when base slug collides."""
        result = generate_model_id("My Model", ["my-model"])
        assert result == "my-model-2"

    def test_increments_suffix_for_multiple_collisions(self):
        """Increments suffix until a unique id is found."""
        result = generate_model_id("My Model", ["my-model", "my-model-2", "my-model-3"])
        assert result == "my-model-4"

    def test_falls_back_to_model_for_empty_name(self):
        """Uses 'model' fallback when name has no usable chars."""
        result = generate_model_id("!!!", [])
        assert result == "model"

    def test_falls_back_when_fallback_collides(self):
        """Appends suffix to fallback when 'model' is taken."""
        result = generate_model_id("!!!", ["model"])
        assert result == "model-2"

    def test_rewrites_custom_preset_id(self):
        """Avoids collision with reserved CUSTOM_PRESET_ID."""
        result = generate_model_id("custom", [])
        assert result == "custom-model"

    def test_rewrites_custom_preset_id_when_taken(self):
        """Avoids collision when custom-model is already taken."""
        result = generate_model_id("custom", ["custom-model"])
        assert result == "custom-model-2"

    def test_does_not_append_suffix_when_no_collision(self):
        """Returns base slug when it is already unique."""
        result = generate_model_id("Unique Model", ["other-model"])
        assert result == "unique-model"
