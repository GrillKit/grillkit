# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Async HTTP client for the Judge0 CE submissions API."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.coding.services.judge0_config import (
    _DEFAULT_CPU_TIME_LIMIT_SECONDS,
    _DEFAULT_MEMORY_LIMIT_KB,
    judge0_auth_token,
    judge0_url,
)

JUDGE0_STATUS_ACCEPTED = 3
JUDGE0_STATUS_TIME_LIMIT = 5
JUDGE0_STATUS_COMPILATION_ERROR = 6
JUDGE0_STATUS_RUNTIME_ERROR = 11


@dataclass(frozen=True, slots=True)
class Judge0SubmissionResult:
    """Normalized Judge0 submission response.

    Attributes:
        status_id: Judge0 status identifier.
        status_description: Human-readable status label.
        stdout: Captured standard output.
        stderr: Captured standard error.
        compile_output: Compiler diagnostics when compilation fails.
        time: CPU time reported by Judge0 (string seconds).
        memory: Memory usage reported by Judge0 in kilobytes.
    """

    status_id: int | None
    status_description: str | None
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    time: str | None
    memory: int | None

    @property
    def duration_ms(self) -> int | None:
        """Return CPU time converted to milliseconds when available."""
        if not self.time:
            return None
        try:
            return int(float(self.time) * 1000)
        except ValueError:
            return None


class Judge0Client:
    """Thin wrapper around Judge0 CE HTTP endpoints."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        auth_token: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Judge0 API base URL; defaults to ``JUDGE0_URL``.
            auth_token: Optional ``X-Auth-Token`` value.
            timeout_seconds: HTTP timeout for submission calls.
        """
        self._base_url = (base_url or judge0_url()).rstrip("/")
        self._auth_token = auth_token if auth_token is not None else judge0_auth_token()
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> Judge0Client:
        """Build a client from environment variables.

        Returns:
            Configured ``Judge0Client`` instance.
        """
        return cls()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["X-Auth-Token"] = self._auth_token
        return headers

    async def health_check(self) -> bool:
        """Return whether the Judge0 server responds to ``/about``.

        Returns:
            True when the health endpoint returns HTTP 200.
        """
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(
                    f"{self._base_url}/about",
                    headers=self._headers(),
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def submit(
        self,
        *,
        source_code: str,
        language_id: int,
        stdin: str = "",
        cpu_time_limit: float | None = None,
        memory_limit_kb: int | None = None,
        compile_only: bool = False,
    ) -> Judge0SubmissionResult:
        """Create a Judge0 submission and wait for the result.

        Args:
            source_code: Program source to execute.
            language_id: Judge0 language identifier.
            stdin: Input passed to the program.
            cpu_time_limit: CPU time limit in seconds.
            memory_limit_kb: Memory limit in kilobytes.
            compile_only: When True, compile without running the program.

        Returns:
            Normalized submission result.

        Raises:
            httpx.HTTPError: If the Judge0 API request fails.
            ValueError: If the response body is invalid.
        """
        payload = {
            "source_code": source_code,
            "language_id": language_id,
            "stdin": stdin,
            "cpu_time_limit": cpu_time_limit or _DEFAULT_CPU_TIME_LIMIT_SECONDS,
            "memory_limit": memory_limit_kb or _DEFAULT_MEMORY_LIMIT_KB,
            "compile_only": compile_only,
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/submissions",
                params={"base64_encoded": "false", "wait": "true"},
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            msg = "Invalid Judge0 response: expected object"
            raise ValueError(msg)
        status = data.get("status") or {}
        return Judge0SubmissionResult(
            status_id=status.get("id"),
            status_description=status.get("description"),
            stdout=data.get("stdout"),
            stderr=data.get("stderr"),
            compile_output=data.get("compile_output"),
            time=data.get("time"),
            memory=data.get("memory"),
        )
