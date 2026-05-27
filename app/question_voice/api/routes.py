# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-voice HTTP routes (Piper status and download)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.platform.api.deps import ConfigServiceDep
from app.question_voice.api.deps import PiperVoiceServiceDep
from app.question_voice.services.status import QuestionVoiceStatusService
from app.shared.api.negotiated_response import negotiated_response

router = APIRouter(prefix="/speech", tags=["question-voice"])


@router.get("/tts/status")
async def tts_status(
    request: Request,
    config_service: ConfigServiceDep,
) -> Response:
    """Return Piper question-voice status for config and interview banners.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.

    Returns:
        HTML partial or JSON status payload.
    """
    config = config_service.get_config()
    status, enabled = QuestionVoiceStatusService.resolve_for_config(config)
    return negotiated_response(
        request,
        QuestionVoiceStatusService.api_payload(status, enabled=enabled),
        "speech_tts_status.html",
        {"status": status, "enabled": enabled},
    )


@router.post("/tts/voice/download")
async def tts_voice_download(
    request: Request,
    config_service: ConfigServiceDep,
    piper_voice_service: PiperVoiceServiceDep,
) -> Response:
    """Start downloading the configured Piper voice for question audio.

    Args:
        request: FastAPI request object.
        config_service: App configuration service.
        piper_voice_service: Piper voice download service.

    Returns:
        HTML partial or JSON status payload after scheduling work.
    """
    config = config_service.get_config()
    if config is None:
        return JSONResponse(
            {"error": "App configuration required"},
            status_code=400,
        )
    if not config.question_voice_enabled:
        return JSONResponse(
            {"error": "Question voice is disabled in configuration"},
            status_code=400,
        )
    status = await piper_voice_service.start_download(
        config.tts_voice_id,
        config.locale,
    )
    return negotiated_response(
        request,
        QuestionVoiceStatusService.api_payload(status, enabled=True),
        "speech_tts_status.html",
        {"status": status, "enabled": True},
    )
