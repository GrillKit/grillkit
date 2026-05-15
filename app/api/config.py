# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Configuration endpoints."""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.config import ConfigService, ProviderConfig
from ..ai.factory import ProviderFactory

router = APIRouter(prefix="/config", tags=["config"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration page.

    Args:
        request: FastAPI request object.

    Returns:
        HTML response with configuration form.
    """
    config = ConfigService.get_config()
    providers = ProviderFactory.get_provider_types()
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
    provider_type: str = Form(...),
    base_url: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(""),
    timeout: float = Form(60.0),
):
    """Save configuration.

    Args:
        request: FastAPI request object.
        provider_type: Type of AI provider.
        base_url: API endpoint URL.
        model: Model name to use.
        api_key: API key for authentication.
        timeout: Request timeout in seconds.

    Returns:
        HTML response with success message or error.
    """
    config = ProviderConfig(
        provider_type=provider_type,
        base_url=base_url,
        model=model,
        api_key=api_key or None,
        timeout=timeout,
    )

    success, message = await ConfigService.test_connection(config)
    if not success:
        providers = ProviderFactory.get_provider_types()
        return templates.TemplateResponse(
            request,
            "config.html",
            {
                "error": message,
                "config": config.to_dict(mask_secret=False),
                "providers": providers,
            },
        )

    ConfigService.save_config(config)
    return templates.TemplateResponse(
        request,
        "config_success.html",
        {
            "message": "Configuration saved successfully",
        },
    )


@router.delete("", response_class=HTMLResponse)
async def delete_config(request: Request):
    """Delete configuration.

    Args:
        request: FastAPI request object.

    Returns:
        HTML response with empty form.
    """
    ConfigService.delete_config()
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "config": None,
            "providers": ProviderFactory.get_provider_types(),
            "message": "Configuration removed",
        },
    )


@router.post("/test", response_class=HTMLResponse)
async def test_config(
    request: Request,
    provider_type: str = Form(...),
    base_url: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(""),
    timeout: float = Form(60.0),
):
    """Test connection without saving.

    Args:
        request: FastAPI request object.
        provider_type: Type of AI provider.
        base_url: API endpoint URL.
        model: Model name to use.
        api_key: API key for authentication.
        timeout: Request timeout in seconds.

    Returns:
        HTML response with test result.
    """
    config = ProviderConfig(
        provider_type=provider_type,
        base_url=base_url,
        model=model,
        api_key=api_key or None,
        timeout=timeout,
    )

    success, message = await ConfigService.test_connection(config)
    return templates.TemplateResponse(
        request,
        "config_test_result.html",
        {
            "success": success,
            "message": message,
        },
    )

