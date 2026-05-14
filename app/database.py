# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Database connection and session management.

This module provides database connectivity, session management,
and SQLAlchemy models for the GrillKit application.
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/grillkit.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Interview(Base):
    """Interview history record.

    Attributes:
        id: Unique interview identifier.
        level: Interview difficulty level.
        category: Question category (e.g., "python", "sql").
        started_at: Timestamp when interview began.
        completed_at: Timestamp when interview ended (None if active).
        status: Interview status ("active", "completed", etc.).
        score: Final interview score (None if not graded).
        messages_json: JSON string of conversation messages.
    """

    __tablename__ = "interviews"

    id = Column(String, primary_key=True)
    level = Column(String, nullable=False)
    category = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="active")
    score = Column(Integer, nullable=True)
    messages_json = Column(String, default="[]")


def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Get database session."""
    return SessionLocal()
