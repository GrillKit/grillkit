# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding feature availability checks for setup and session creation."""

import asyncio
import os

import httpx

from app.coding.services.judge0_config import judge0_auth_token, judge0_url

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _coding_enabled_env() -> bool:
    """Return whether coding is enabled via ``CODING_ENABLED``.

    Returns:
        True when coding is enabled in the environment.
    """
    return os.environ.get("CODING_ENABLED", "true").lower() in _TRUTHY


def is_judge0_healthy() -> bool:
    """Probe Judge0 synchronously for setup and validation paths.

    Returns:
        True when ``GET /about`` responds with HTTP 200.
    """
    try:
        headers: dict[str, str] = {}
        token = judge0_auth_token()
        if token:
            headers["X-Auth-Token"] = token
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{judge0_url()}/about", headers=headers)
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def is_judge0_healthy_async() -> bool:
    """Probe Judge0 asynchronously for async API handlers.

    Returns:
        True when ``GET /about`` responds with HTTP 200.
    """
    from app.coding.services.judge0_client import Judge0Client

    return await Judge0Client.from_env().health_check()


def is_coding_available() -> bool:
    """Return whether coding can be selected on setup and created.

    Requires ``CODING_ENABLED`` and a healthy Judge0 instance.

    Returns:
        True when coding sessions may be started from setup.
    """
    if not _coding_enabled_env():
        return False
    return is_judge0_healthy()


async def is_coding_available_async() -> bool:
    """Async variant of :func:`is_coding_available` for API handlers.

    Returns:
        True when coding sessions may be started from setup.
    """
    if not _coding_enabled_env():
        return False
    return await is_judge0_healthy_async()


def run_is_coding_available_async() -> bool:
    """Run the async availability probe from synchronous code.

    Returns:
        True when coding sessions may be started from setup.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(is_coding_available_async())
    msg = "run_is_coding_available_async() cannot be used inside a running event loop"
    raise RuntimeError(msg)
