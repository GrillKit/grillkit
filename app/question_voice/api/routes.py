# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Question-voice HTTP routes (Piper status and download)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.platform.api.deps import ConfigServiceDep
from app.platform.services.config import ProviderConfig
from app.question_voice.api.deps import PiperVoiceServiceDep
from app.question_voice.domain.voices import default_voice_for_locale
from app.question_voice.services.piper_voice import PiperVoiceService, PiperVoiceStatus
from app.shared.api.negotiated_response import negotiated_response

router = APIRouter(prefix="/speech", tags=["question-voice"])


def _status_for_config(config: ProviderConfig | None) -> tuple[PiperVoiceStatus, bool]:
    """Resolve Piper voice status and whether question voice is enabled.

    Args:
        config: Saved provider configuration, if any.

    Returns:
        Voice status snapshot and enabled flag for API consumers.
    """
    if config is None or not config.question_voice_enabled:
        voice_id = (
            config.tts_voice_id
            if config is not None
            else default_voice_for_locale("en")
        )
        locale = config.locale if config is not None else "en"
        return (
            PiperVoiceStatus(
                voice_id=voice_id,
                locale=locale,
                locale_label="English",
                state="missing",
                percent=0,
                message="Question voice is disabled in configuration.",
                voice_display_name=voice_id,
            ),
            False,
        )

    return (
        PiperVoiceService.get_status(config.tts_voice_id, config.locale),
        True,
    )


def _status_payload(status: PiperVoiceStatus, *, enabled: bool) -> dict[str, object]:
    """Serialize Piper voice status for JSON responses.

    Args:
        status: Piper voice status snapshot.
        enabled: Whether question voice is enabled in configuration.

    Returns:
        JSON-serializable status dictionary.
    """
    state = status.state if enabled else "unavailable"
    return {
        "voice_id": status.voice_id,
        "locale": status.locale,
        "locale_label": status.locale_label,
        "state": state,
        "percent": status.percent,
        "message": status.message,
        "voice_display_name": status.voice_display_name,
        "loaded_in_memory": status.loaded_in_memory,
        "enabled": enabled,
    }


def _status_response(
    request: Request,
    status: PiperVoiceStatus,
    *,
    enabled: bool,
) -> Response:
    """Return HTML fragment or JSON depending on the Accept header.

    Args:
        request: FastAPI request object.
        status: Piper voice status snapshot.
        enabled: Whether question voice is enabled in configuration.

    Returns:
        Template or JSON response.
    """
    return negotiated_response(
        request,
        _status_payload(status, enabled=enabled),
        "speech_tts_status.html",
        {"status": status, "enabled": enabled},
    )


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
    status, enabled = _status_for_config(config)
    return _status_response(request, status, enabled=enabled)


@router.post("/tts/voice/download")
async def tts_voice_download(
    request: Request,
    config_service: ConfigServiceDep,
    piper_voice_service: PiperVoiceServiceDep,
) -> Response:
    """Start downloading the configured Piper voice for question audio.

    Args:
        request: FastAPI request object.
        config_service: Provider configuration service.
        piper_voice_service: Piper voice download service.

    Returns:
        HTML partial or JSON status payload after scheduling work.
    """
    config = config_service.get_config()
    if config is None:
        return JSONResponse(
            {"error": "Provider configuration required"},
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
    return _status_response(request, status, enabled=True)
