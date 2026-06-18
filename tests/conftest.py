# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration and shared fixtures."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.coding.domain.value_objects import CodingRunResult
from app.coding.services.judge0_client import Judge0Client, Judge0SubmissionResult
from app.interview.repositories.uow import InterviewUnitOfWork
from app.main import create_app
from app.platform.services.config import AppConfig
from app.shared.infrastructure import models  # noqa: F401 - registers all ORM models
from app.shared.infrastructure.database import Base
from tests.fakes import FakeProvider


@pytest.fixture
def client():
    """Create a test client with mocked database init."""
    with (
        patch("app.main.run_migrations"),
        patch(
            "app.platform.services.speech_runtime.SpeechRuntimeCoordinator.startup",
            new=AsyncMock(),
        ),
        patch(
            "app.platform.services.speech_runtime.SpeechRuntimeCoordinator.unload_all",
        ),
    ):
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture
def minimal_app_config() -> AppConfig:
    """Minimal saved provider configuration for API tests."""
    return AppConfig(
        provider_type="openai-compatible",
        base_url="http://localhost",
        model="gpt-4",
    )


@pytest.fixture
def isolated_db(monkeypatch):
    """Route all UnitOfWork sessions to an in-memory SQLite database.

    Yields:
        SQLAlchemy engine bound to the in-memory database.
    """
    from app.shared.infrastructure import database as db_module

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(db_module, "SessionLocal", testing_session)
    monkeypatch.setattr(db_module, "engine", engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fake_ai_provider() -> Callable[[list[str]], FakeProvider]:
    """Build a ``FakeProvider`` for injection into interview services.

    Returns:
        Callable that accepts reply strings and returns the fake provider.
    """

    def _make(replies: list[str]) -> FakeProvider:
        return FakeProvider(replies)

    return _make


def fake_judge0_client(return_result: CodingRunResult | None = None) -> Judge0Client:
    """Build a Judge0Client whose ``submit`` always returns a predetermined result.

    Args:
        return_result: Result returned by ``submit``; defaults to a fake success run.

    Returns:
        Stubbed ``Judge0Client`` usable via ``CodingRunnerService.run_public_tests``.
    """
    from tests.helpers.fake_judge0 import fake_coding_run_result

    result = return_result or fake_coding_run_result()
    client = Judge0Client(base_url="http://fake-judge0", timeout_seconds=5.0)

    async def _stub_submit(**_kwargs: Any) -> Judge0SubmissionResult:
        # Map CodingRunResult back to Judge0SubmissionResult
        status_id = 3 if result.status == "success" else 6
        return Judge0SubmissionResult(
            status_id=status_id,
            status_description="Accepted" if result.status == "success" else "Error",
            stdout=result.stdout,
            stderr=result.stderr,
            compile_output=result.compile_output,
            time=str(result.duration_ms / 1000) if result.duration_ms else None,
            memory=None,
        )

    client.submit = _stub_submit  # type: ignore[method-assign]
    return client


@pytest.fixture
def mock_judge0(monkeypatch):
    """Globally patch ``CodingRunnerService`` to use a fake Judge0.

    The returned helper can be called per-test to set a custom result::

        def test_run(mock_judge0):
            mock_judge0(status="compile_error")
            ...

    Yields:
        Callable ``(status=...) -> None`` that reconfigures the global patch.
    """
    from app.coding.services.runner import CodingRunnerService
    from tests.helpers.fake_judge0 import (
        FakeRunConfig,
        fake_compile_error_result,
        fake_coding_run_result,
        fake_tests_failed_result,
    )

    _current_result: CodingRunResult = fake_coding_run_result()

    async def _fake_run_public_tests(
        *,
        source_code: str,
        task_spec: dict[str, Any],
        client: Judge0Client | None = None,
    ) -> CodingRunResult:
        del source_code, task_spec, client
        return _current_result

    async def _fake_run_hidden_tests(
        *,
        source_code: str,
        task_spec: dict[str, Any],
        client: Judge0Client | None = None,
    ) -> CodingRunResult:
        del source_code, task_spec, client
        return _current_result

    monkeypatch.setattr(
        CodingRunnerService,
        "run_public_tests",
        staticmethod(_fake_run_public_tests),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        CodingRunnerService,
        "run_hidden_tests",
        staticmethod(_fake_run_hidden_tests),  # type: ignore[arg-type]
    )

    def _configure(
        *,
        status: str | None = None,
        config: FakeRunConfig | None = None,
    ) -> None:
        nonlocal _current_result
        if status == "compile_error":
            _current_result = fake_compile_error_result()
        elif status == "tests_failed":
            _current_result = fake_tests_failed_result()
        elif config is not None:
            _current_result = fake_coding_run_result(config)
        else:
            _current_result = fake_coding_run_result()

    yield _configure

    # Reset to default after each test
    _current_result = fake_coding_run_result()


@pytest.fixture
def override_ws_ai_provider() -> Callable:
    """Override the interview WebSocket AI provider dependency on a test client.

    Returns:
        Callable ``(test_client, replies) -> FakeProvider``.
    """
    from app.interview.api.deps import get_ai_provider

    def _apply(test_client, replies: list[str]) -> FakeProvider:
        provider = FakeProvider(replies)

        async def _dep():
            yield provider

        test_client.app.dependency_overrides[get_ai_provider] = _dep
        return provider

    return _apply


@pytest.fixture
def uow(isolated_db):
    """Yield a committed InterviewUnitOfWork using the isolated in-memory database.

    Yields:
        InterviewUnitOfWork instance with auto_commit enabled.
    """
    del isolated_db
    with InterviewUnitOfWork(auto_commit=True) as work:
        yield work


@pytest.fixture
def minimal_config_saved(client):
    """Save a minimal provider configuration so routes do not redirect to /config.

    Yields:
        Response from the POST /config save call.
    """
    response = client.post(
        "/config",
        data={
            "llm_preset_id": "preset-fake",
            "api_key": "",
            "timeout": "60",
            "locale": "en",
            "speech_model_size": "small",
            "question_voice_enabled": "",
        },
    )
    yield response


pytest_plugins = ["tests.shared.test_questions"]
