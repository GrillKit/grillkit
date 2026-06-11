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
from app.shared.infrastructure.database import Base
from app.shared.paths import ALEMBIC_INI
from tests.helpers.legacy_interview import insert_pre_session_mode_interview


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
        """Legacy language keys become track and selection_spec ends at v2 at head."""
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
        insert_pre_session_mode_interview(
            session,
            interview_id="legacy-interview",
            selection_spec=legacy_spec,
        )
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")

        session = session_factory()
        row = session.execute(
            text("SELECT selection_spec, session_mode FROM interviews WHERE id = :id"),
            {"id": "legacy-interview"},
        ).one()
        data = json.loads(row.selection_spec)
        assert data["version"] == 2
        assert data["session_mode"] == "theory_only"
        assert data["theory"]["sources"][0]["track"] == "python"
        assert "language" not in data["theory"]["sources"][0]
        assert row.session_mode == "theory_only"
        session.close()

    def test_track_migration_is_idempotent(self, alembic_engine):
        """Running migrations twice leaves v2 rows unchanged."""
        track_spec = (
            '{"sources":[{"track":"database","level":"junior",'
            '"categories":["sql-basics"]}]}'
        )
        session_factory = sessionmaker(bind=alembic_engine)
        session = session_factory()
        insert_pre_session_mode_interview(
            session,
            interview_id="track-interview",
            selection_spec=track_spec,
            question_count=3,
            question_time_limit_seconds=90,
        )
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")
        command.upgrade(alembic_cfg, "head")

        with alembic_engine.connect() as conn:
            stored = conn.execute(
                text(
                    "SELECT selection_spec, session_mode FROM interviews WHERE id = :id"
                ),
                {"id": "track-interview"},
            ).one()
        data = json.loads(stored.selection_spec)
        assert data["version"] == 2
        assert data["session_mode"] == "theory_only"
        assert data["theory"]["question_count"] == 3
        assert data["theory"]["task_time_limit_seconds"] == 90
        assert stored.session_mode == "theory_only"
