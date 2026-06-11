# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for theory section domain, repository, and migration."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.models import Interview, TheorySection
from app.shared.paths import ALEMBIC_INI
from app.theory.domain.entities import TheorySection as DomainTheorySection
from app.theory.domain.entities import TheoryTask
from app.theory.domain.value_objects import PlannedTheoryQuestion
from app.theory.repositories.uow import TheoryUnitOfWork
from tests.helpers.legacy_interview import insert_pre_session_mode_interview


def _sample_selection() -> InterviewSelection:
    return InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("basics",),
            ),
        )
    )


def _sample_planned() -> tuple[PlannedTheoryQuestion, ...]:
    return (
        PlannedTheoryQuestion(
            id="py-001",
            text="What is a list?",
            code=None,
        ),
        PlannedTheoryQuestion(
            id="py-002",
            text="Explain dict.",
            code="d = {}",
        ),
    )


class TestTheoryTaskTimer:
    """Theory task timer behavior mirrors legacy answer rounds."""

    def test_timer_deadline_and_expiry(self) -> None:
        """Timer helpers respect grace and remaining seconds."""
        started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        task = TheoryTask(
            id=1,
            theory_section_id=10,
            interview_id="iv-1",
            question_id="py-001",
            order=1,
            round=0,
            question_text="Q",
            question_code=None,
            answer_text=None,
            score=None,
            feedback=None,
            started_at=started,
            created_at=started,
        )
        deadline = task.timer_deadline(120)
        assert deadline == started + timedelta(seconds=120)
        assert not task.is_timer_expired(120, now=started + timedelta(seconds=119))
        assert task.is_timer_expired(120, now=started + timedelta(seconds=122))
        assert task.remaining_seconds(120, now=started + timedelta(seconds=30)) == 90


class TestTheorySectionDomain:
    """Theory section aggregate factory."""

    def test_start_builds_tasks_with_timer_on_first(self) -> None:
        """First task gets started_at when a time limit is configured."""
        section = DomainTheorySection.start(
            "iv-1",
            selection=_sample_selection(),
            locale="en",
            planned_questions=_sample_planned(),
            task_time_limit_seconds=90,
        )
        assert section.question_count == 2
        assert section.status == "active"
        assert section.tasks[0].started_at is not None
        assert section.tasks[1].started_at is None


class TestTheorySectionRepository:
    """Theory section persistence."""

    def test_create_aggregate_persists_tasks(self, isolated_db) -> None:
        """Repository round-trips a theory section with linked answer rows."""
        with TheoryUnitOfWork() as uow:
            uow.session.add(
                Interview(
                    id="iv-theory",
                    selection_spec='{"sources":[{"track":"python","level":"junior","categories":["basics"]}]}',
                )
            )
            uow.commit()

        section = DomainTheorySection.start(
            "iv-theory",
            selection=_sample_selection(),
            locale="en",
            planned_questions=_sample_planned(),
            task_time_limit_seconds=120,
        )
        with TheoryUnitOfWork() as uow:
            created = uow.theory_sections.create_aggregate(section)
            uow.commit()

        assert created.id > 0
        assert created.interview_id == "iv-theory"
        assert created.task_time_limit_seconds == 120
        assert len(created.tasks) == 2
        assert created.tasks[0].id != TheoryTask.NEW_ID
        assert created.question_ids == ("py-001", "py-002")

        with TheoryUnitOfWork() as uow:
            loaded = uow.theory_sections.get_aggregate("iv-theory")

        assert loaded is not None
        assert loaded.id == created.id
        assert loaded.question_count == 2
        assert len(loaded.tasks) == 2
        assert loaded.tasks[0].theory_section_id == loaded.id


@pytest.fixture
def alembic_engine(tmp_path: Path, monkeypatch):
    """SQLite file DB with Alembic migrations applied through revision 0003."""
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
    command.upgrade(alembic_cfg, "20260526_0003")

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


class TestTheorySectionsAlembicMigration:
    """Tests for theory_sections schema migration."""

    def test_backfills_theory_section_per_interview(self, alembic_engine) -> None:
        """Each interview row gets a matching theory_sections row at head."""
        session_factory = sessionmaker(bind=alembic_engine)
        session = session_factory()
        insert_pre_session_mode_interview(
            session,
            interview_id="legacy-interview",
            selection_spec='{"sources":[{"track":"python","level":"junior","categories":["basics"]}]}',
            question_count=4,
            question_time_limit_seconds=60,
            locale="ru",
        )
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")

        session = session_factory()
        section = (
            session.query(TheorySection)
            .filter_by(interview_id="legacy-interview")
            .one()
        )
        assert section.question_count == 4
        assert section.task_time_limit_seconds == 60
        assert section.locale == "ru"
        assert section.status == "active"
        data = json.loads(section.selection_spec)
        assert data["sources"][0]["track"] == "python"
        session.close()

    def test_backfill_is_idempotent(self, alembic_engine) -> None:
        """Running head migration twice does not duplicate theory sections."""
        session_factory = sessionmaker(bind=alembic_engine)
        session = session_factory()
        insert_pre_session_mode_interview(
            session,
            interview_id="dup-interview",
            selection_spec='{"sources":[{"track":"database","level":"junior","categories":["sql-basics"]}]}',
        )
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")
        command.upgrade(alembic_cfg, "head")

        with alembic_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM theory_sections WHERE interview_id = :id"),
                {"id": "dup-interview"},
            ).scalar_one()
        assert count == 1

    def test_backfills_theory_section_id_on_answers(self, alembic_engine) -> None:
        """Answers migration links rows to their parent theory section."""
        session_factory = sessionmaker(bind=alembic_engine)
        session = session_factory()
        insert_pre_session_mode_interview(
            session,
            interview_id="answers-link",
            selection_spec='{"sources":[{"track":"python","level":"junior","categories":["basics"]}]}',
            question_count=1,
        )
        session.close()

        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "20260608_0004")

        session = session_factory()
        section_id = (
            session.query(TheorySection.id)
            .filter_by(interview_id="answers-link")
            .scalar()
        )
        session.execute(
            text(
                """
                INSERT INTO answers (
                    interview_id, question_id, "order", round, question_text, created_at
                )
                VALUES (
                    :interview_id, :question_id, :order, :round, :question_text,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "interview_id": "answers-link",
                "question_id": "q1",
                "order": 1,
                "round": 0,
                "question_text": "Question?",
            },
        )
        session.commit()
        session.close()

        command.upgrade(alembic_cfg, "20260608_0005")

        session = session_factory()
        answer = session.execute(
            text(
                """
                SELECT theory_section_id
                FROM answers
                WHERE question_id = :question_id
                """
            ),
            {"question_id": "q1"},
        ).one()
        assert answer.theory_section_id == section_id
        session.close()
