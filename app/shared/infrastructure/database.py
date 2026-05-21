# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database connection and session management.

This module provides database connectivity, session management,
and the declarative base for all SQLAlchemy models.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.paths import DB_DIR

DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_DIR}/grillkit.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def init_db() -> None:
    """Create all tables if they don't exist.

    Imports models to ensure they are registered with Base.metadata,
    then creates tables.
    """
    import app.shared.infrastructure.models  # noqa: F401 - register models with Base

    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Get a new database session.

    Returns:
        A new SQLAlchemy Session instance.
    """
    return SessionLocal()
