# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database connection and session management.

This module provides database connectivity, session management,
and the declarative base for all SQLAlchemy models.
"""

import os

from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from alembic import command
from app.shared.paths import ALEMBIC_INI, DB_DIR

DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DB_DIR}/grillkit.db",
)


def _configure_sqlite_connection(
    dbapi_connection: object,
    _connection_record: object,
) -> None:
    """Enable WAL mode and a busy timeout for concurrent SQLite access.

    Args:
        dbapi_connection: DB-API connection from the SQLAlchemy pool.
        _connection_record: SQLAlchemy connection record (unused).
    """
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )
    event.listen(engine, "connect", _configure_sqlite_connection)
else:
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def run_migrations() -> None:
    """Apply Alembic migrations up to head."""
    alembic_cfg = Config(str(ALEMBIC_INI))
    command.upgrade(alembic_cfg, "head")
