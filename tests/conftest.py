# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration and shared fixtures."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.uow import UnitOfWork
from tests.fakes import FakeProvider


@pytest.fixture
def isolated_db(monkeypatch):
    """Route all UnitOfWork sessions to an in-memory SQLite database.

    Yields:
        SQLAlchemy engine bound to the in-memory database.
    """
    from app import database as db_module
    from app import uow as uow_module

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(db_module, "SessionLocal", testing_session)
    monkeypatch.setattr(uow_module, "SessionLocal", testing_session)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def patch_ai_provider(monkeypatch) -> Callable[[list[str]], FakeProvider]:
    """Patch ``ai_provider_from_config`` to yield a ``FakeProvider``.

    Returns:
        Callable that accepts reply strings and installs the fake provider.
    """

    def _install(replies: list[str]) -> FakeProvider:
        provider = FakeProvider(replies)

        @asynccontextmanager
        async def _fake_context() -> AsyncIterator[FakeProvider]:
            yield provider

        monkeypatch.setattr(
            "app.services.answer_processing.ai_provider_from_config",
            _fake_context,
        )
        monkeypatch.setattr(
            "app.services.interview_completion.ai_provider_from_config",
            _fake_context,
        )
        return provider

    return _install


@pytest.fixture
def uow(isolated_db):
    """Yield a committed UnitOfWork using the isolated in-memory database.

    Yields:
        UnitOfWork instance with auto_commit enabled.
    """
    del isolated_db
    with UnitOfWork(auto_commit=True) as work:
        yield work


pytest_plugins = ["tests.test_questions"]
