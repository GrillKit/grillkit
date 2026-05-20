# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from app.api.deps import ConfigServiceDep
from app.services.config import ProviderConfig
from app.templating import templates

router = APIRouter(prefix="/config", tags=["config"])


async def _config_from_form(
    config_service: ConfigServiceDep,
    provider_type: str = Form(...),
    base_url: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(""),
    timeout: float = Form(60.0),
) -> tuple[ProviderConfig, bool, str]:
    """Parse the config form, build ProviderConfig, and test the connection."""
    config = ProviderConfig(
        provider_type=provider_type,
        base_url=base_url,
        model=model,
        api_key=api_key or None,
        timeout=timeout,
    )
    success, message = await config_service.test_connection(config)
    return config, success, message


ConfigFromForm = Annotated[tuple[ProviderConfig, bool, str], Depends(_config_from_form)]


@router.get("", response_class=HTMLResponse)
async def config_page(
    request: Request, config_service: ConfigServiceDep
) -> HTMLResponse:
    """Configuration page.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.

    Returns:
        HTML response with configuration form.
    """
    config = config_service.get_config()
    providers = config_service.get_provider_types()
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "config": config.to_dict(mask_secret=True) if config else None,
            "providers": providers,
        },
    )


@router.post("", response_class=HTMLResponse)
async def save_config(
    request: Request,
    form: ConfigFromForm,
    config_service: ConfigServiceDep,
) -> HTMLResponse:
    """Save configuration.

    Args:
        request: FastAPI request object.
        form: Parsed form fields and connection test result.
        config_service: Provider configuration service.

    Returns:
        HTML response with success message or error.
    """
    config, success, message = form
    if not success:
        return templates.TemplateResponse(
            request,
            "config.html",
            {
                "error": message,
                "config": config.to_dict(mask_secret=False),
                "providers": config_service.get_provider_types(),
            },
        )

    config_service.save_config(config)
    return templates.TemplateResponse(
        request,
        "config_success.html",
        {"message": "Configuration saved successfully"},
    )


@router.delete("", response_class=HTMLResponse)
async def delete_config(
    request: Request, config_service: ConfigServiceDep
) -> HTMLResponse:
    """Delete configuration.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.

    Returns:
        HTML response with empty form.
    """
    config_service.delete_config()
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "config": None,
            "providers": config_service.get_provider_types(),
            "message": "Configuration removed",
        },
    )


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
