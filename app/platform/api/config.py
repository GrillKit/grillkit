# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from app.platform.api.deps import (
    AddLLMModelUseCaseDep,
    ConfigServiceDep,
    DeleteConfigUseCaseDep,
    SaveConfigUseCaseDep,
)
from app.platform.domain.config import AppConfig
from app.platform.queries.config_form import parse_and_test
from app.platform.queries.platform_page import build_page_context
from app.platform.schemas import NewLLMModel
from app.platform.use_cases.add_llm_model import AddLLMModelResult
from app.shared.locales import DEFAULT_LOCALE
from app.shared.speech_models import DEFAULT_SPEECH_MODEL_SIZE
from app.speech.api.deps import WhisperModelServiceDep
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
) -> tuple[AppConfig, bool, str]:
    """Parse the config form, build AppConfig, and test the connection."""
    return await parse_and_test(
        config_service,
        llm_preset_id=llm_preset_id,
        api_key=api_key,
        timeout=timeout,
        locale=locale,
        speech_model_size=speech_model_size,
        question_voice_enabled=question_voice_enabled,
    )


ConfigFromForm = Annotated[tuple[AppConfig, bool, str], Depends(_config_from_form)]


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
    context = (
        await build_page_context(
            config=config,
            whisper_model_service=whisper_model_service,
        )
    ).model_dump()
    return templates.TemplateResponse(request, "config.html", context)


@router.post("", response_class=HTMLResponse)
async def save_config(
    request: Request,
    form: ConfigFromForm,
    whisper_model_service: WhisperModelServiceDep,
    save_config: SaveConfigUseCaseDep,
) -> HTMLResponse:
    """Save configuration.

    Args:
        request: FastAPI request object.
        form: Parsed form fields and connection test result.
        whisper_model_service: Whisper model download service.
        save_config: Use case that persists config and reloads speech runtimes.

    Returns:
        HTML response with success message or error.
    """
    config, success, message = form
    if not success:
        context = (
            await build_page_context(
                config=config,
                whisper_model_service=whisper_model_service,
                error=message,
                mask_secret=False,
            )
        ).model_dump()
        return templates.TemplateResponse(request, "config.html", context)

    result = await save_config.execute(config)
    if result.speech_errors:
        # Config is saved, but one of the speech models failed to load.
        # Warn the user instead of silently ignoring the failure.
        warning = (
            "Configuration saved, but a speech model failed to load: "
            + " | ".join(result.speech_errors)
        )
        context = (
            await build_page_context(
                config=config,
                whisper_model_service=whisper_model_service,
                message=warning,
            )
        ).model_dump()
        return templates.TemplateResponse(request, "config.html", context)
    return templates.TemplateResponse(
        request,
        "config_success.html",
        {"message": "Configuration saved successfully"},
    )


@router.delete("", response_class=HTMLResponse)
async def delete_config(
    request: Request,
    whisper_model_service: WhisperModelServiceDep,
    delete_config: DeleteConfigUseCaseDep,
) -> HTMLResponse:
    """Delete configuration.

    Args:
        request: FastAPI request object.
        whisper_model_service: Whisper model download service.
        delete_config: Use case that removes config and unloads speech runtimes.

    Returns:
        HTML response with empty form.
    """
    delete_config.execute()
    context = (
        await build_page_context(
            config=None,
            whisper_model_service=whisper_model_service,
            message="Configuration removed",
        )
    ).model_dump()
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
    add_model: AddLLMModelUseCaseDep,
    display_name: str = Form(...),
    base_url: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(""),
    api_key_required: bool = Form(False),
    accepts_audio_input: bool = Form(False),
) -> HTMLResponse:
    """Add a user-defined OpenAI-compatible model to the catalog.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.
        add_model: Use case that probes and persists the new catalog entry.
        display_name: Label shown in the interview model selector.
        base_url: OpenAI-compatible API base URL.
        model: Provider model name.
        api_key: Optional API key stored with the catalog entry.
        api_key_required: Whether the saved provider config needs an API key.
        accepts_audio_input: Whether the catalog entry supports audio answers.

    Returns:
        Configuration page with a success or validation error message.
    """
    try:
        payload = NewLLMModel(
            display_name=display_name,
            base_url=base_url,
            model=model,
            api_key=api_key,
            api_key_required=api_key_required,
            accepts_audio_input=accepts_audio_input,
        )
    except ValidationError as exc:
        result = AddLLMModelResult(error=exc.errors()[0]["msg"])
    else:
        result = await add_model.execute(payload)
    context = (
        await build_page_context(
            config=config_service.get_config(),
            whisper_model_service=whisper_model_service,
            error=result.error,
            message=result.message,
            selected_llm_preset_id=result.selected_preset_id,
        )
    ).model_dump()
    return templates.TemplateResponse(request, "config.html", context)
