# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""LLM model catalog types."""

from dataclasses import dataclass
import re
from typing import Final

CUSTOM_PRESET_ID: Final[str] = "custom"
MODEL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"
)


@dataclass(frozen=True)
class LLMModelEntry:
    """One OpenAI-compatible interview model from the catalog.

    Attributes:
        id: Stable model identifier stored in ``data/llm_models.json``.
        display_name: Human-readable label for the configuration UI.
        provider_type: Provider adapter id (always ``openai-compatible`` today).
        model: Model name passed to the provider API.
        base_url: OpenAI-compatible API base URL.
        api_key_required: Whether the UI should prompt for an API key.
        api_key: Stored API key for catalog entries (optional).
    """

    id: str
    display_name: str
    provider_type: str
    model: str
    base_url: str
    api_key_required: bool
    api_key: str | None = None


@dataclass(frozen=True)
class LLMCatalog:
    """User-defined model catalog loaded from ``data/llm_models.json``.

    Attributes:
        selected_id: Active interview model id, if any.
        models: All models keyed by id.
    """

    selected_id: str | None
    models: dict[str, LLMModelEntry]


def normalize_model_id(model_id: str, catalog: LLMCatalog) -> str:
    """Return a supported catalog model id.

    Args:
        model_id: Raw model id from storage or form input.
        catalog: Loaded model catalog.

    Returns:
        Normalized model id.

    Raises:
        ValueError: If ``model_id`` is empty/invalid or unknown.
    """
    value = model_id.strip()
    if not value or value == CUSTOM_PRESET_ID:
        raise ValueError("Interview model is required")
    if value not in catalog.models:
        raise ValueError(f"Unsupported LLM model: {value}")
    return value


def validate_new_model_id(model_id: str) -> str:
    """Normalize and validate a user-supplied catalog model id.

    Args:
        model_id: Proposed model id from the add-model form.

    Returns:
        Normalized lowercase id.

    Raises:
        ValueError: If the id is invalid or reserved.
    """
    value = model_id.strip().lower()
    if not value:
        raise ValueError("Model id is required")
    if value == CUSTOM_PRESET_ID:
        raise ValueError(f"Model id '{CUSTOM_PRESET_ID}' is reserved")
    if not MODEL_ID_PATTERN.fullmatch(value):
        raise ValueError(
            "Model id must use lowercase letters, digits, and hyphens only"
        )
    return value
