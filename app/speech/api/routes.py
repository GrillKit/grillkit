# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech model download and status endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.platform.api.deps import ConfigServiceDep
from app.shared.api.negotiated_response import negotiated_response
from app.speech.api.deps import WhisperModelServiceDep
from app.speech.schemas.options import SpeechModelOptionRead
from app.speech.services.rules.speech_models import SPEECH_MODEL_BY_SIZE

router = APIRouter(prefix="/speech", tags=["speech"])


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
    return negotiated_response(
        request,
        status.model_dump(),
        "speech_model_status.html",
        {"status": status},
    )


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
    return negotiated_response(
        request,
        status.model_dump(),
        "speech_model_status.html",
        {"status": status},
    )


@router.get("/model/options")
async def speech_model_options() -> JSONResponse:
    """Return speech model size metadata for UI trade-off hints.

    Returns:
        JSON list of size options with download and performance hints.
    """
    options = [
        SpeechModelOptionRead(
            size=spec.size,
            display_name=spec.display_name,
            approx_download_mb=spec.approx_download_mb,
            ram_hint=spec.ram_hint,
            speed_hint=spec.speed_hint,
            quality_hint=spec.quality_hint,
        ).model_dump()
        for spec in SPEECH_MODEL_BY_SIZE.values()
    ]
    return JSONResponse({"options": options})
