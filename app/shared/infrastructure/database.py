# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database connection and session management.

This module provides database connectivity, session management,
and the declarative base for all SQLAlchemy models.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.paths import DB_DIR, PROJECT_ROOT

ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_DIR}/grillkit.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def run_migrations() -> None:
    """Apply Alembic migrations up to head."""
    from alembic.config import Config

    from alembic import command
    import app.shared.infrastructure.models  # noqa: F401 - register models with Base

    alembic_cfg = Config(str(ALEMBIC_INI))
    command.upgrade(alembic_cfg, "head")


def init_db() -> None:
    """Ensure database schema is up to date via Alembic migrations."""
    run_migrations()


def get_session() -> Session:
    """Get a new database session.

    Returns:
        A new SQLAlchemy Session instance.
    """
    return SessionLocal()
