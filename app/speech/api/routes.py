# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech model download and status endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.platform.api.deps import ConfigServiceDep
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.domain.models import SPEECH_MODEL_BY_SIZE
from app.speech.services.whisper_model import WhisperModelStatus
from app.templating import templates

router = APIRouter(prefix="/speech", tags=["speech"])


def _status_response(
    request: Request,
    status: WhisperModelStatus,
) -> Response:
    """Return HTML fragment or JSON depending on the Accept header."""
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse(
            {
                "size": status.size,
                "locale": status.locale,
                "locale_label": status.locale_label,
                "state": status.state,
                "percent": status.percent,
                "message": status.message,
                "model_display_name": status.model_display_name,
                "loaded_in_memory": status.loaded_in_memory,
            }
        )
    return templates.TemplateResponse(
        request,
        "speech_model_status.html",
        {"status": status},
    )


@router.get("/model/status")
async def speech_model_status(
    request: Request,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> Response:
    """Return installation status for the configured Whisper model size.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML partial or JSON status payload.
    """
    config = config_service.get_config()
    if config is None:
        return JSONResponse(
            {"error": "Provider configuration required"}, status_code=400
        )
    status = whisper_model_service.get_status(
        config.speech_model_size,
        config.locale,
    )
    return _status_response(request, status)


@router.post("/model/download")
async def speech_model_download(
    request: Request,
    config_service: ConfigServiceDep,
    whisper_model_service: WhisperModelServiceDep,
) -> Response:
    """Start downloading the Whisper model for the configured size.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        whisper_model_service: Whisper model download service.

    Returns:
        HTML partial or JSON status payload after scheduling work.
    """
    config = config_service.get_config()
    if config is None:
        return JSONResponse(
            {"error": "Provider configuration required"}, status_code=400
        )
    status = await whisper_model_service.start_download(
        config.speech_model_size,
        config.locale,
    )
    return _status_response(request, status)


@router.get("/model/options")
async def speech_model_options() -> JSONResponse:
    """Return speech model size metadata for UI trade-off hints.

    Returns:
        JSON list of size options with download and performance hints.
    """
    options = [
        {
            "size": spec.size,
            "display_name": spec.display_name,
            "approx_download_mb": spec.approx_download_mb,
            "ram_hint": spec.ram_hint,
            "speed_hint": spec.speed_hint,
            "quality_hint": spec.quality_hint,
        }
        for spec in SPEECH_MODEL_BY_SIZE.values()
    ]
    return JSONResponse({"options": options})
