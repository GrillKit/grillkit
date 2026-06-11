# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding section repository and domain aggregate."""

from dataclasses import replace
from pathlib import Path

from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.coding.domain.entities import CodingSection
from app.coding.domain.value_objects import PlannedCodingTask
from app.coding.repositories.coding_section import CodingSectionRepository
from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Interview
from app.shared.paths import ALEMBIC_INI
from tests.helpers.selection import minimal_selection_spec


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for coding repository tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine):
    """Create a test database session."""
    _Session = sessionmaker(bind=engine)  # noqa: N806
    session = _Session()
    yield session
    session.close()


def _planned_tasks() -> tuple[PlannedCodingTask, ...]:
    return (
        PlannedCodingTask(
            id="bas-004",
            text="Add type hints",
            task_spec={
                "language": "python",
                "evaluation_mode": "ai",
                "starter_code": "def process(data): pass",
            },
        ),
        PlannedCodingTask(
            id="func-006",
            text="Document divide()",
            task_spec={
                "language": "python",
                "evaluation_mode": "ai",
                "starter_code": "def divide(a, b): pass",
            },
        ),
    )


def test_create_and_load_coding_aggregate(db_session) -> None:
    """Repository persists section and tasks and reloads domain aggregate."""
    interview = Interview(
        id="coding-session-1",
        selection_spec=minimal_selection_spec(),
        status="active",
    )
    db_session.add(interview)
    db_session.commit()

    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics", "functions"),
            ),
        )
    )
    section = CodingSection.start(
        interview.id,
        selection=selection,
        locale="en",
        planned_tasks=_planned_tasks(),
        task_time_limit_seconds=600,
    )

    repo = CodingSectionRepository(db_session)
    created = repo.create_aggregate(section)
    db_session.commit()

    assert created.id > 0
    assert created.task_count == 2
    assert len(created.tasks) == 2
    assert created.tasks[0].id > 0
    assert created.tasks[0].task_spec["language"] == "python"

    loaded = repo.get_aggregate(interview.id)
    assert loaded is not None
    assert loaded.task_ids == ("bas-004", "func-006")
    assert loaded.tasks[1].prompt_text == "Document divide()"


def test_coding_section_is_complete_when_all_submitted() -> None:
    """Domain aggregate reports completion only after every task is submitted."""
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics",),
            ),
        )
    )
    section = CodingSection.start(
        "session-1",
        selection=selection,
        locale="en",
        planned_tasks=_planned_tasks()[:1],
    )
    assert section.is_complete() is False

    task = section.tasks[0]
    updated = replace(
        section,
        tasks=(
            replace(
                task,
                submitted_code="def process(data: list[int]) -> list[int]: ...",
                score=4,
            ),
        ),
    )
    assert updated.is_complete() is True
    assert updated.total_score() == 4
    assert updated.max_score() == 5


class TestCodingSectionsAlembicMigration:
    """Tests for coding section schema migration."""

    @pytest.fixture
    def alembic_engine(self, tmp_path: Path, monkeypatch):
        """SQLite file DB upgraded through the coding tables migration."""
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
        command.upgrade(alembic_cfg, "20260609_0008")

        yield engine

        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def test_coding_tables_exist_at_revision(self, alembic_engine) -> None:
        """Migration creates coding_sections, coding_tasks, and code_run_attempts."""
        with alembic_engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name LIKE 'coding%' "
                        "OR name = 'code_run_attempts'"
                    )
                )
            }
        assert "coding_sections" in tables
        assert "coding_tasks" in tables
        assert "code_run_attempts" in tables
