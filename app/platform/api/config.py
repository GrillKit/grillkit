# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from app.platform.api.config_page import build_config_page_context
from app.platform.api.deps import ConfigServiceDep
from app.platform.api.runtime_reload import (
    reload_speech_runtimes_after_config_save,
    unload_speech_runtimes,
)
from app.platform.services.config import ProviderConfig
from app.platform.services.llm_catalog import LLMCatalogService, NewLLMModel
from app.question_voice.domain.voices import default_voice_for_locale
from app.shared.domain.locales import DEFAULT_LOCALE, normalize_locale
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.domain.models import (
    DEFAULT_SPEECH_MODEL_SIZE,
    normalize_speech_model_size,
)
from app.templating import templates

router = APIRouter(prefix="/config", tags=["config"])


async def _config_from_form(
    config_service: ConfigServiceDep,
    llm_preset_id: str = Form(...),
    api_key: str = Form(""),
    timeout: float = Form(60.0),
    locale: str = Form(DEFAULT_LOCALE),
    speech_model_size: str = Form(DEFAULT_SPEECH_MODEL_SIZE),
    question_voice_enabled: bool = Form(False),
) -> tuple[ProviderConfig, bool, str]:
    """Parse the config form, build ProviderConfig, and test the connection."""
    existing = config_service.get_config()
    try:
        normalized_preset_id = LLMCatalogService.normalize_model_id(llm_preset_id)
    except ValueError as exc:
        fallback = existing or ProviderConfig(
            provider_type="openai-compatible",
            base_url="",
            model="",
            locale=normalize_locale(locale),
            speech_model_size=normalize_speech_model_size(speech_model_size),
            question_voice_enabled=question_voice_enabled,
        )
        return fallback, False, str(exc)

    entry = LLMCatalogService.get_model(normalized_preset_id)
    if entry is None:
        return (
            existing
            or ProviderConfig(
                provider_type="openai-compatible",
                base_url="",
                model="",
            ),
            False,
            "Interview model not found",
        )

    config = ProviderConfig(
        provider_type=entry.provider_type,
        base_url=entry.base_url,
        model=entry.model,
        api_key=ProviderConfig.resolve_api_key_from_form(api_key, normalized_preset_id),
        timeout=timeout,
        locale=normalize_locale(locale),
        speech_model_size=normalize_speech_model_size(speech_model_size),
        question_voice_enabled=question_voice_enabled,
        tts_voice_id=(
            existing.tts_voice_id
            if existing
            else default_voice_for_locale(normalize_locale(locale))
        ),
        llm_preset_id=normalized_preset_id,
    )
    success, message = await config_service.test_connection(config)
    return config, success, message


ConfigFromForm = Annotated[tuple[ProviderConfig, bool, str], Depends(_config_from_form)]


@router.get("", response_class=HTMLResponse)
async def config_page(
    request: Request,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> HTMLResponse:
    """Configuration page.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML response with configuration form.
    """
    config = config_service.get_config()
    context = await build_config_page_context(
        config=config,
        whisper_model_service=whisper_model_service,
    )
    return templates.TemplateResponse(request, "config.html", context)


@router.post("", response_class=HTMLResponse)
async def save_config(
    request: Request,
    form: ConfigFromForm,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> HTMLResponse:
    """Save configuration.

    Args:
        request: FastAPI request object.
        form: Parsed form fields and connection test result.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML response with success message or error.
    """
    config, success, message = form
    if not success:
        context = await build_config_page_context(
            config=config,
            whisper_model_service=whisper_model_service,
            error=message,
            mask_secret=False,
        )
        return templates.TemplateResponse(request, "config.html", context)

    config_service.save_config(config)
    await reload_speech_runtimes_after_config_save(config)
    return templates.TemplateResponse(
        request,
        "config_success.html",
        {"message": "Configuration saved successfully"},
    )


@router.delete("", response_class=HTMLResponse)
async def delete_config(
    request: Request,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> HTMLResponse:
    """Delete configuration.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML response with empty form.
    """
    config_service.delete_config()
    unload_speech_runtimes()
    context = await build_config_page_context(
        config=None,
        whisper_model_service=whisper_model_service,
        message="Configuration removed",
    )
    return templates.TemplateResponse(request, "config.html", context)


@router.post("/test", response_class=HTMLResponse)
async def test_config(request: Request, form: ConfigFromForm) -> HTMLResponse:
    """Test connection without saving.

    Args:
        request: FastAPI request object.
        form: Parsed form fields and connection test result.

    Returns:
        HTML response with test result.
    """
    _config, success, message = form
    return templates.TemplateResponse(
        request,
        "config_test_result.html",
        {"success": success, "message": message},
    )


@router.post("/llm-models", response_class=HTMLResponse)
async def add_llm_model(
    request: Request,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
    model_id: str = Form(...),
    display_name: str = Form(...),
    base_url: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(""),
    api_key_required: bool = Form(False),
) -> HTMLResponse:
    """Add a user-defined OpenAI-compatible model to the catalog.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.
        model_id: Stable lowercase catalog id.
        display_name: Label shown in the interview model selector.
        base_url: OpenAI-compatible API base URL.
        model: Provider model name.
        api_key: Optional API key stored with the catalog entry.
        api_key_required: Whether the saved provider config needs an API key.

    Returns:
        Configuration page with a success or validation error message.
    """
    config = config_service.get_config()
    selected_preset_id: str | None = None
    try:
        entry = LLMCatalogService.add_user_model(
            NewLLMModel(
                model_id=model_id,
                display_name=display_name,
                base_url=base_url,
                model=model,
                api_key_required=api_key_required,
                api_key=api_key.strip() or None,
            )
        )
        selected_preset_id = entry.id
        message = f"Added model '{entry.display_name}' to the catalog."
        error = None
    except ValueError as exc:
        message = None
        error = str(exc)

    context = await build_config_page_context(
        config=config,
        whisper_model_service=whisper_model_service,
        error=error,
        message=message,
    )
    if selected_preset_id is not None:
        context["selected_llm_preset_id"] = selected_preset_id
    return templates.TemplateResponse(request, "config.html", context)
