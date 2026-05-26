# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Alembic selection_spec data migration."""

import json
from pathlib import Path

from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.shared.infrastructure.database import ALEMBIC_INI, Base
from app.shared.infrastructure.models import Interview


@pytest.fixture
def alembic_engine(tmp_path: Path, monkeypatch):
    """SQLite file DB with Alembic migrations applied."""
    db_path = tmp_path / "grillkit.db"
    db_url = f"sqlite:///{db_path}"

    import app.shared.infrastructure.database as database_module

    engine = create_engine(db_url, echo=False)
    monkeypatch.setattr(database_module, "DATABASE_URL", db_url)
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(
        database_module,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=engine),
    )

    alembic_cfg = Config(str(ALEMBIC_INI))
    command.upgrade(alembic_cfg, "20260526_0001")

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


class TestSelectionSpecAlembicMigration:
    """Tests for selection_spec data migrations."""

    def test_migrates_legacy_selection_spec_rows(self, alembic_engine):
        """Legacy language keys become track; version field is removed at head."""
        legacy_spec = json.dumps(
            {
                "version": 1,
                "sources": [
                    {
                        "language": "python",
                        "level": "junior",
                        "categories": ["basics"],
                    }
                ],
            },
            separators=(",", ":"),
        )
        session_factory = sessionmaker(bind=alembic_engine)
        session = session_factory()
        session.add(
            Interview(
                id="legacy-interview",
                selection_spec=legacy_spec,
            )
        )
        session.commit()
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")

        session = session_factory()
        row = session.get(Interview, "legacy-interview")
        assert row is not None
        data = json.loads(row.selection_spec)
        assert "version" not in data
        assert data["sources"][0]["track"] == "python"
        assert "language" not in data["sources"][0]
        session.close()

    def test_track_migration_is_idempotent(self, alembic_engine):
        """Running migrations twice leaves modern rows unchanged."""
        track_spec = (
            '{"sources":[{"track":"database","level":"junior",'
            '"categories":["sql-basics"]}]}'
        )
        session_factory = sessionmaker(bind=alembic_engine)
        session = session_factory()
        session.add(
            Interview(
                id="track-interview",
                selection_spec=track_spec,
            )
        )
        session.commit()
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")
        command.upgrade(alembic_cfg, "head")

        with alembic_engine.connect() as conn:
            stored = conn.execute(
                text("SELECT selection_spec FROM interviews WHERE id = :id"),
                {"id": "track-interview"},
            ).scalar_one()
        assert stored == track_spec
