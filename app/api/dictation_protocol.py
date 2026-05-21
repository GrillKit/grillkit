# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""WebSocket JSON protocol for interview dictation."""

from typing import Any, Final

DICTATION_CLIENT_START: Final[str] = "start"
DICTATION_CLIENT_STOP: Final[str] = "stop"

DICTATION_SERVER_FINAL: Final[str] = "final"
DICTATION_SERVER_ERROR: Final[str] = "error"
DICTATION_SERVER_READY: Final[str] = "ready"


def dictation_message(msg_type: str, **fields: Any) -> dict[str, Any]:
    """Build a dictation WebSocket JSON message.

    Args:
        msg_type: Message type discriminator.
        **fields: Additional payload fields.

    Returns:
        JSON-serializable message dict.
    """
    return {"type": msg_type, **fields}
