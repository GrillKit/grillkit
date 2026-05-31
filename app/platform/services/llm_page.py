# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""LLM catalog read models for configuration templates."""

from app.platform.schemas import LLMPresetOptionRead
from app.platform.services.config import AppConfig
from app.platform.services.llm_catalog import LLMCatalogService


class LLMPageService:
    """Build LLM catalog sections for the configuration page."""

    @staticmethod
    def list_preset_options() -> list[LLMPresetOptionRead]:
        """Load catalog entries for the interview model selector.

        Returns:
            Preset read models for ``config_form.html``.
        """
        return [
            LLMPresetOptionRead(
                id=entry.id,
                display_name=entry.display_name,
                description=entry.model,
                model=entry.model,
                base_url=entry.base_url,
                api_key_required=entry.api_key_required,
                accepts_audio_input=entry.accepts_audio_input,
            )
            for entry in LLMCatalogService.list_models()
        ]

    @staticmethod
    def resolve_selected_preset_id(config: AppConfig | None) -> str | None:
        """Return the active catalog model id for the configuration form.

        Args:
            config: Saved provider configuration, if any.

        Returns:
            Selected preset id from config or catalog storage.
        """
        selected_id = LLMCatalogService.get_selected_model_id()
        if config is not None and config.llm_preset_id:
            return config.llm_preset_id
        return selected_id
