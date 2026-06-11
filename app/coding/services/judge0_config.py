# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Judge0 connection settings and language identifiers."""

import os

JUDGE0_LANGUAGE_IDS: dict[str, int] = {
    "python": 71,
}

_DEFAULT_JUDGE0_URL = "http://localhost:2358"
_DEFAULT_CPU_TIME_LIMIT_SECONDS = 5.0
_DEFAULT_MEMORY_LIMIT_KB = 128_000


def judge0_url() -> str:
    """Return the Judge0 API base URL without a trailing slash.

    Returns:
        Base URL from ``JUDGE0_URL`` or the local development default.
    """
    return os.environ.get("JUDGE0_URL", _DEFAULT_JUDGE0_URL).rstrip("/")


def judge0_auth_token() -> str | None:
    """Return the optional Judge0 auth token.

    Returns:
        Token string, or None when unset.
    """
    token = os.environ.get("JUDGE0_AUTH_TOKEN", "").strip()
    return token or None


def judge0_language_id(language: str) -> int:
    """Map a GrillKit language slug to a Judge0 language ID.

    Args:
        language: Language slug from a coding task spec.

    Returns:
        Judge0 language identifier.

    Raises:
        ValueError: If the language is not supported in v1.
    """
    language_id = JUDGE0_LANGUAGE_IDS.get(language)
    if language_id is None:
        msg = f"Unsupported Judge0 language: {language}"
        raise ValueError(msg)
    return language_id
