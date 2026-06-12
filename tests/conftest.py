# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration and shared fixtures."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.interview.repositories.uow import InterviewUnitOfWork
from app.main import create_app
from app.platform.services.config import AppConfig
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


pytest_plugins = ["tests.shared.test_questions"]
