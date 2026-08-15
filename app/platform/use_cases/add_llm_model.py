# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Use case for adding a user-defined LLM model to the catalog."""

from dataclasses import dataclass

from pydantic import ValidationError

from app.platform.domain.config import AppConfig, ConfigService
from app.platform.domain.llm_catalog import LLMCatalogService
from app.platform.schemas import NewLLMModel
from app.shared.locales import DEFAULT_LOCALE
from app.shared.speech_models import DEFAULT_SPEECH_MODEL_SIZE


@dataclass(frozen=True)
class AddLLMModelResult:
    """Outcome of adding a model to the catalog.

    Attributes:
        error: Optional validation or connection error message.
        message: Optional success message.
        selected_preset_id: Catalog id to preselect on the config page.
    """

    error: str | None = None
    message: str | None = None
    selected_preset_id: str | None = None


class AddLLMModelUseCase:
    """Probe a user-defined model and append it to the catalog.

    The full add flow lives here instead of the HTTP handler: build the
    probe config from the submitted form, verify the provider connection,
    and only persist the entry when the probe succeeds.
    """

    def __init__(
        self,
        config_service: type[ConfigService],
        llm_catalog_service: type[LLMCatalogService],
    ) -> None:
        self._config_service: type[ConfigService] = config_service
        self._catalog_service: type[LLMCatalogService] = llm_catalog_service

    async def execute(
        self,
        *,
        display_name: str,
        base_url: str,
        model: str,
        api_key: str,
        api_key_required: bool,
        accepts_audio_input: bool,
    ) -> AddLLMModelResult:
        """Run the add-model flow.

        Args:
            display_name: Label shown in the interview model selector.
            base_url: OpenAI-compatible API base URL.
            model: Provider model name.
            api_key: Optional API key stored with the catalog entry.
            api_key_required: Whether the saved provider config needs an API key.
            accepts_audio_input: Whether the catalog entry supports audio answers.

        Returns:
            Result with an error or success message for the config page.
        """
        config = self._config_service.get_config()
        try:
            payload = NewLLMModel(
                display_name=display_name,
                base_url=base_url,
                model=model,
                api_key_required=api_key_required,
                api_key=api_key,
                accepts_audio_input=accepts_audio_input,
            )
            speech_model_size = (
                config.speech_model_size
                if config is not None
                else DEFAULT_SPEECH_MODEL_SIZE
            )
            probe_config = AppConfig(
                provider_type="openai-compatible",
                base_url=payload.base_url,
                model=payload.model,
                api_key=payload.api_key,
                speech_model_size=speech_model_size,
                locale=config.locale if config is not None else DEFAULT_LOCALE,
            )
            success, test_message = await self._config_service.test_catalog_model(
                probe_config,
                accepts_audio_input=payload.accepts_audio_input,
            )
            if not success:
                raise ValueError(test_message)
            entry = self._catalog_service.add_user_model(payload)
            return AddLLMModelResult(
                message=f"Added model '{entry.display_name}' to the catalog.",
                selected_preset_id=entry.id,
            )
        except ValidationError as exc:
            return AddLLMModelResult(error=exc.errors()[0]["msg"])
        except ValueError as exc:
            return AddLLMModelResult(error=str(exc))
