# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Piper TTS voice metadata keyed by voice id and interview locale."""

from dataclasses import dataclass
from typing import Final

from app.shared.locales import normalize_locale

DEFAULT_TTS_VOICE_ID: Final[str] = "en_US-lessac-medium"


@dataclass(frozen=True)
class PiperVoiceSpec:
    """Published Piper voice for one locale tier.

    Attributes:
        voice_id: Piper voice identifier (directory name under piper-voices).
        locale: GrillKit interview locale code this voice supports.
        display_name: Human-readable label for UI.
        hf_repo_relpath: Path prefix inside ``rhasspy/piper-voices`` on Hugging Face.
        approx_download_mb: Approximate download size for trade-off hints.
        quality_hint: Relative synthesis quality expectation.
    """

    voice_id: str
    locale: str
    display_name: str
    hf_repo_relpath: str
    approx_download_mb: int
    quality_hint: str


PIPER_VOICES_BY_ID: Final[dict[str, PiperVoiceSpec]] = {
    "en_US-lessac-medium": PiperVoiceSpec(
        voice_id="en_US-lessac-medium",
        locale="en",
        display_name="Lessac (US English, medium)",
        hf_repo_relpath="en/en_US/lessac/medium",
        approx_download_mb=63,
        quality_hint="Clear US English; good default for interviews",
    ),
    "ru_RU-dmitri-medium": PiperVoiceSpec(
        voice_id="ru_RU-dmitri-medium",
        locale="ru",
        display_name="Dmitri (Russian, medium)",
        hf_repo_relpath="ru/ru_RU/dmitri/medium",
        approx_download_mb=63,
        quality_hint="Natural Russian pronunciation",
    ),
    "fr_FR-siwis-medium": PiperVoiceSpec(
        voice_id="fr_FR-siwis-medium",
        locale="fr",
        display_name="Siwis (French, medium)",
        hf_repo_relpath="fr/fr_FR/siwis/medium",
        approx_download_mb=63,
        quality_hint="Standard French accent",
    ),
    "es_ES-davefx-medium": PiperVoiceSpec(
        voice_id="es_ES-davefx-medium",
        locale="es",
        display_name="Davefx (Spanish, medium)",
        hf_repo_relpath="es/es_ES/davefx/medium",
        approx_download_mb=63,
        quality_hint="European Spanish",
    ),
    "de_DE-thorsten-medium": PiperVoiceSpec(
        voice_id="de_DE-thorsten-medium",
        locale="de",
        display_name="Thorsten (German, medium)",
        hf_repo_relpath="de/de_DE/thorsten/medium",
        approx_download_mb=63,
        quality_hint="Standard German pronunciation",
    ),
}

_DEFAULT_VOICE_BY_LOCALE: Final[dict[str, str]] = {
    spec.locale: spec.voice_id for spec in PIPER_VOICES_BY_ID.values()
}


def normalize_tts_voice_id(voice_id: str) -> str:
    """Return a supported Piper voice id or raise ``ValueError``.

    Args:
        voice_id: Requested Piper voice identifier.

    Returns:
        Normalized voice id present in ``PIPER_VOICES_BY_ID``.

    Raises:
        ValueError: If the voice id is not in the catalog.
    """
    code = voice_id.strip()
    if code not in PIPER_VOICES_BY_ID:
        supported = ", ".join(sorted(PIPER_VOICES_BY_ID))
        raise ValueError(
            f"Unsupported TTS voice id '{voice_id}'. Choose one of: {supported}"
        )
    return code


def voice_spec_for_id(voice_id: str) -> PiperVoiceSpec:
    """Return Piper voice metadata for a supported voice id.

    Args:
        voice_id: Piper voice identifier.

    Returns:
        Voice metadata for the id.

    Raises:
        ValueError: If the voice id is not supported.
    """
    code = normalize_tts_voice_id(voice_id)
    return PIPER_VOICES_BY_ID[code]


def default_voice_for_locale(locale: str) -> str:
    """Return the default Piper voice id for a supported locale.

    Args:
        locale: Interview locale code.

    Returns:
        Default ``voice_id`` for the locale.

    Raises:
        ValueError: If the locale is not supported or has no default voice.
    """
    code = normalize_locale(locale)
    voice_id = _DEFAULT_VOICE_BY_LOCALE.get(code)
    if voice_id is None:
        raise ValueError(f"No default Piper voice configured for locale '{locale}'")
    return voice_id
