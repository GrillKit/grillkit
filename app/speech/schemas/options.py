# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Speech model option read models for JSON APIs."""

from pydantic import BaseModel, ConfigDict


class SpeechModelOptionRead(BaseModel):
    """Speech model size metadata for setup and config UI.

    Attributes:
        size: Model size slug (e.g. ``small``).
        display_name: Human-readable label.
        approx_download_mb: Approximate download size in megabytes.
        ram_hint: RAM usage guidance for the UI.
        speed_hint: Speed trade-off hint.
        quality_hint: Quality trade-off hint.
    """

    model_config = ConfigDict(frozen=True)

    size: str
    display_name: str
    approx_download_mb: int
    ram_hint: str
    speed_hint: str
    quality_hint: str
