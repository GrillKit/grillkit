# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Template context helpers for the LLM model catalog on HTML pages."""

from typing import Any

from app.ai.llm_models import LLMModelEntry
from app.platform.services.config import ProviderConfig
from app.platform.services.llm_catalog import LLMCatalogService


def _model_description(entry: LLMModelEntry) -> str:
    """Build a short UI description for one catalog entry."""
    return entry.model


async def build_llm_page_context(config: ProviderConfig | None) -> dict[str, Any]:
    """Build LLM catalog keys for the configuration page.

    Args:
        config: Saved provider configuration, if any.

    Returns:
        Dict with ``llm_presets`` and ``selected_llm_preset_id``.
    """
    models = LLMCatalogService.list_models()
    preset_options = [
        {
            "id": entry.id,
            "display_name": entry.display_name,
            "description": _model_description(entry),
            "model": entry.model,
            "base_url": entry.base_url,
            "api_key_required": entry.api_key_required,
        }
        for entry in models
    ]

    selected_id = LLMCatalogService.get_selected_model_id()
    if config is not None and config.llm_preset_id:
        selected_id = config.llm_preset_id

    return {
        "llm_presets": preset_options,
        "selected_llm_preset_id": selected_id,
    }
