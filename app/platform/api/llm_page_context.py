# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Template context helpers for the LLM model catalog on HTML pages."""

from typing import Any

from app.platform.services.config import AppConfig
from app.platform.services.llm_page import LLMPageService


async def build_llm_page_context(config: AppConfig | None) -> dict[str, Any]:
    """Build LLM catalog keys for the configuration page.

    Args:
        config: Saved provider configuration, if any.

    Returns:
        Dict with ``llm_presets`` and ``selected_llm_preset_id``.
    """
    return {
        "llm_presets": [
            preset.model_dump() for preset in LLMPageService.list_preset_options()
        ],
        "selected_llm_preset_id": LLMPageService.resolve_selected_preset_id(config),
    }
