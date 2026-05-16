# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database connection and session management.

This module provides database connectivity, session management,
and the declarative base for all SQLAlchemy models.
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/grillkit.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create all tables if they don't exist.

    Imports models to ensure they are registered with Base.metadata,
    then creates tables.
    """
    from . import models  # noqa: F401 - register models with Base

    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Get a new database session.

    Returns:
        A new SQLAlchemy Session instance.
    """
    return SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations.

    Automatically commits on success and rolls back on exception.
    The session is closed when the block exits.

    Yields:
        SQLAlchemy Session instance.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
