# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Load and persist the interview LLM model catalog from ``data/llm_models.json``."""

import json
from typing import Any

from app.ai.llm_models import LLMCatalog, LLMModelEntry
from app.paths import LLM_MODELS_PATH
from app.platform.schemas import NewLLMModel


class LLMCatalogService:
    """Read and update the user LLM model catalog."""

    @staticmethod
    def load_catalog() -> LLMCatalog:
        """Load models from ``data/llm_models.json``.

        Returns:
            Catalog with selected id and all saved models.
        """
        data = _read_catalog_file()
        models = _parse_models(data["models"])
        selected_id = str(data["selected"]).strip() or None
        return LLMCatalog(selected_id=selected_id, models=models)

    @staticmethod
    def get_selected_model_id() -> str | None:
        """Return the active interview model id from ``data/llm_models.json``.

        Returns:
            Selected model id or ``None`` when unset or unknown.
        """
        catalog = LLMCatalogService.load_catalog()
        if catalog.selected_id and catalog.selected_id in catalog.models:
            return catalog.selected_id
        return next(iter(catalog.models), None)

    @staticmethod
    def set_selected_model(model_id: str) -> None:
        """Persist the active interview model id.

        Args:
            model_id: Catalog model id to mark as selected.

        Raises:
            ValueError: If the model id is unknown.
        """
        if model_id not in LLMCatalogService.load_catalog().models:
            raise ValueError(f"Unsupported LLM model: {model_id}")
        data = _read_catalog_file()
        data["selected"] = model_id
        _write_catalog_file(data)

    @staticmethod
    def get_model(model_id: str | None) -> LLMModelEntry | None:
        """Look up one catalog entry by id.

        Args:
            model_id: Catalog model id or ``None``.

        Returns:
            Matching entry, or ``None`` when unset or unknown.
        """
        if not model_id:
            return None
        return LLMCatalogService.load_catalog().models.get(model_id)

    @staticmethod
    def list_models() -> list[LLMModelEntry]:
        """Return catalog models sorted by display name.

        Returns:
            Ordered list of model entries for UI selection.
        """
        catalog = LLMCatalogService.load_catalog()
        return sorted(
            catalog.models.values(),
            key=lambda entry: (entry.display_name.lower(), entry.id),
        )

    @staticmethod
    def add_user_model(payload: NewLLMModel) -> LLMModelEntry:
        """Append a model to ``data/llm_models.json``.

        Args:
            payload: Validated add-model form values.

        Returns:
            Persisted catalog entry.

        Raises:
            ValueError: If the id is invalid or already exists.
        """
        model_id = payload.model_id

        data = _read_catalog_file()
        models = dict(data["models"])
        if model_id in models:
            raise ValueError(f"Model id '{model_id}' already exists")

        api_key = payload.api_key
        api_key_required = payload.api_key_required or bool(api_key)
        entry_dict = _model_dict(
            display_name=payload.display_name,
            model_name=payload.model,
            base_url=payload.base_url,
            api_key_required=api_key_required,
            api_key=api_key,
            accepts_audio_input=payload.accepts_audio_input,
        )
        models[model_id] = entry_dict
        data["models"] = models
        data["selected"] = model_id
        _write_catalog_file(data)
        return _parse_model(model_id, entry_dict)

    @staticmethod
    def update_model_api_key(model_id: str, api_key: str | None) -> None:
        """Persist an API key for a catalog model.

        Args:
            model_id: Catalog model id.
            api_key: API key to store, or ``None`` to remove it.
        """
        data = _read_catalog_file()
        models = dict(data["models"])
        raw_entry = models.get(model_id)
        if not isinstance(raw_entry, dict):
            return
        entry = dict(raw_entry)
        if api_key:
            entry["api_key"] = api_key
            entry["api_key_required"] = True
        else:
            entry.pop("api_key", None)
        models[model_id] = entry
        data["models"] = models
        _write_catalog_file(data)

    @staticmethod
    def save_model_selection(model_id: str, api_key: str | None) -> None:
        """Persist the active model and optional API key update.

        Args:
            model_id: Catalog model id selected for interviews.
            api_key: API key to store when provided on save.
        """
        LLMCatalogService.set_selected_model(model_id)
        if api_key:
            LLMCatalogService.update_model_api_key(model_id, api_key)


def _model_dict(
    *,
    display_name: str,
    model_name: str,
    base_url: str,
    api_key_required: bool,
    api_key: str | None = None,
    provider_type: str = "openai-compatible",
    accepts_audio_input: bool = False,
) -> dict[str, Any]:
    """Build a catalog entry dictionary for persistence."""
    entry: dict[str, Any] = {
        "display_name": display_name,
        "provider_type": provider_type,
        "model": model_name,
        "base_url": base_url,
        "api_key_required": api_key_required,
        "accepts_audio_input": accepts_audio_input,
    }
    if api_key:
        entry["api_key"] = api_key
    return entry


def _read_catalog_file() -> dict[str, Any]:
    """Return catalog JSON, seeding an empty file when missing."""
    if not LLM_MODELS_PATH.exists():
        LLM_MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
        empty: dict[str, Any] = {"selected": "", "models": {}}
        LLM_MODELS_PATH.write_text(json.dumps(empty, indent=2))
        return empty
    data: dict[str, Any] = json.loads(LLM_MODELS_PATH.read_text())
    data.setdefault("selected", "")
    data.setdefault("models", {})
    return data


def _write_catalog_file(data: dict[str, Any]) -> None:
    """Persist catalog JSON to disk."""
    LLM_MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "selected": str(data["selected"]).strip(),
        "models": data["models"],
    }
    LLM_MODELS_PATH.write_text(json.dumps(payload, indent=2))


def _parse_models(raw: dict[str, Any]) -> dict[str, LLMModelEntry]:
    """Parse a models mapping from catalog JSON."""
    parsed: dict[str, LLMModelEntry] = {}
    for model_id, item in raw.items():
        if isinstance(item, dict):
            parsed[model_id] = _parse_model(model_id, item)
    return parsed


def _parse_model(model_id: str, item: dict[str, Any]) -> LLMModelEntry:
    """Parse one catalog model entry."""
    base_url = str(item.get("base_url", "")).strip().rstrip("/")
    raw_api_key = item.get("api_key")
    api_key = str(raw_api_key).strip() if raw_api_key else None
    return LLMModelEntry(
        id=model_id,
        display_name=str(item.get("display_name", model_id)),
        provider_type=str(item.get("provider_type", "openai-compatible")),
        model=str(item.get("model", "")),
        base_url=base_url,
        api_key_required=bool(item.get("api_key_required", False)),
        api_key=api_key,
        accepts_audio_input=bool(item.get("accepts_audio_input", False)),
    )
