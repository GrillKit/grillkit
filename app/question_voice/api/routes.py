# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-voice HTTP routes (Piper status and download)."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.platform.api.deps import ConfigServiceDep
from app.question_voice.api.deps import PiperVoiceServiceDep
from app.question_voice.services.status import QuestionVoiceStatusService
from app.shared.api.negotiated_response import negotiated_response

router = APIRouter(prefix="/speech", tags=["question-voice"])


@router.get("/tts/status")
async def tts_status(
    request: Request,
    config_service: ConfigServiceDep,
    locale: str | None = Query(default=None),
    voice_id: str | None = Query(default=None),
) -> Response:
    """Return Piper question-voice status for config and interview banners.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        locale: Interview locale when provider config is not saved yet.
        voice_id: Piper voice id when provider config is not saved yet.

    Returns:
        HTML partial or JSON status payload.
    """
    config = config_service.get_config()
    status, enabled = QuestionVoiceStatusService.resolve_for_config(
        config,
        locale=locale,
        voice_id=voice_id,
    )
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
    locale: str | None = Query(default=None),
    voice_id: str | None = Query(default=None),
) -> Response:
    """Start downloading the configured Piper voice for question audio.

    Args:
        request: FastAPI request object.
        config_service: App configuration service.
        piper_voice_service: Piper voice download service.
        locale: Interview locale when provider config is not saved yet.
        voice_id: Piper voice id when provider config is not saved yet.

    Returns:
        HTML partial or JSON status payload after scheduling work.
    """
    config = config_service.get_config()
    resolved_voice, resolved_locale = QuestionVoiceStatusService.resolve_tts_target(
        config,
        locale=locale,
        voice_id=voice_id,
    )
    status = await piper_voice_service.start_download(
        resolved_voice,
        resolved_locale,
    )
    enabled = config is not None and config.question_voice_enabled
    return negotiated_response(
        request,
        QuestionVoiceStatusService.api_payload(status, enabled=enabled),
        "speech_tts_status.html",
        {"status": status, "enabled": enabled},
    )
