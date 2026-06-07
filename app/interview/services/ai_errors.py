# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""User-facing AI provider error messages for interview clients."""


def ai_error_message_for_client(exc: Exception) -> str:
    """Turn provider failures into a short client error message.

    Args:
        exc: Exception raised during AI evaluation.

    Returns:
        User-facing error message.
    """
    text = str(exc)
    if "not found" in text.lower() and "model" in text.lower():
        return (
            "AI model is not available on the configured endpoint. "
            "Open /config and verify the model name and provider settings."
        )
    if "timed out" in text.lower() or "timeout" in text.lower():
        return (
            "AI evaluation timed out. The model may still be loading — "
            "wait and try again, or increase the timeout on /config."
        )
    return f"AI evaluation failed: {text}"
