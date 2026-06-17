# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for multi-section session phase transitions."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from app.coding.domain.value_objects import CodingRunResult
from app.coding.services.page import CodingPageService
from app.coding.services.section import CodingSectionService
from app.interview.domain.value_objects import (
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.phases import SessionPhaseOrchestrator
from app.theory.services.section import TheorySectionService
from tests.helpers.session_creation import create_session


def _theory_then_coding_session() -> SessionSelection:
    """Build a minimal theory-then-coding session selection for tests."""
    return SessionSelection(
        session_mode="theory_then_coding",
        theory=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=120,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("data-structures",),
                ),
            ),
        ),
        coding=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=600,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
        ),
    )


def _complete_theory_section(interview_id: str) -> None:
    """Mark every theory task in a section as answered."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        section = uow.theory_sections.get_aggregate(interview_id)
        assert section is not None
        tasks = tuple(
            replace(task, answer_text="done", score=5) for task in section.tasks
        )
        uow.theory_sections.save_aggregate(replace(section, tasks=tasks))


def test_pending_coding_section_does_not_start_timer_at_creation(
    isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Pending coding sections defer the task timer until the coding phase begins."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = create_session(
        _theory_then_coding_session(),
        locale="en",
    )

    with InterviewUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    assert section.status == "pending"
    assert section.tasks[0].started_at is None


def test_coding_then_theory_defers_theory_timer_until_theory_phase(
    isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Theory timers start only after the coding phase when theory comes second."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    session = SessionSelection(
        session_mode="coding_then_theory",
        theory=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=120,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("data-structures",),
                ),
            ),
        ),
        coding=SectionBranchSpec(
            enabled=True,
            question_count=1,
            task_time_limit_seconds=600,
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
        ),
    )
    interview = create_session(session, locale="en")

    with InterviewUnitOfWork() as uow:
        theory = uow.theory_sections.get_aggregate(interview.id)
    assert theory is not None
    assert theory.tasks[0].started_at is None

    with InterviewUnitOfWork() as uow:
        coding = uow.coding_sections.get_aggregate(interview.id)
    assert coding is not None
    assert coding.status == "active"
    assert coding.tasks[0].started_at is not None


def test_activate_pending_promotes_coding_after_theory_complete(
    isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Pending coding sections become active once theory is finished."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = create_session(
        _theory_then_coding_session(),
        locale="en",
    )

    with InterviewUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    assert section.status == "pending"
    with InterviewUnitOfWork(auto_commit=True) as uow:
        coding = CodingSectionService(uow)
        assert coding.activate_pending(interview.id) is False

    _complete_theory_section(interview.id)
    with InterviewUnitOfWork() as uow:
        theory = TheorySectionService(uow)
        assert theory.is_complete(interview.id) is True

    with InterviewUnitOfWork(auto_commit=True) as uow:
        coding = CodingSectionService(uow)
        assert coding.activate_pending(interview.id) is True

    with InterviewUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    assert section.status == "active"
    assert section.tasks[0].started_at is not None


def test_notify_theory_complete_activates_pending_coding(
    isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Theory phase completion hook activates the next coding section."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = create_session(
        _theory_then_coding_session(),
        locale="en",
    )
    _complete_theory_section(interview.id)

    with (
        patch.object(TheorySectionService, "on_phase_complete"),
        InterviewUnitOfWork(auto_commit=True) as uow,
    ):
        SessionPhaseOrchestrator(uow).notify_section_complete(
            interview.id,
            "theory",
        )

    with InterviewUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    assert section.status == "active"


def test_coding_run_works_after_theory_phase_activation(
    client, isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Run API accepts requests once the coding section is activated."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = create_session(
        _theory_then_coding_session(),
        locale="en",
    )
    _complete_theory_section(interview.id)
    with InterviewUnitOfWork(auto_commit=True) as uow:
        CodingPageService(uow).activate_timer(interview.id)

    with InterviewUnitOfWork() as uow:
        section = uow.coding_sections.get_aggregate(interview.id)
    assert section is not None
    task_id = section.tasks[0].task_id

    run_result = CodingRunResult(
        status="success",
        stdout=None,
        stderr=None,
        compile_output=None,
        tests_passed=0,
        tests_total=0,
        test_results=(),
        duration_ms=5,
    )
    with patch(
        "app.coding.services.run_execution.CodingRunnerService.run_public_tests",
        new=AsyncMock(return_value=run_result),
    ):
        response = client.post(
            f"/interview/{interview.id}/coding/run",
            json={"task_id": task_id, "source_code": "def solve():\n    return 1"},
        )

    assert response.status_code == 200
    assert response.json()["attempt_no"] == 1


def test_interview_page_switches_to_coding_template_after_theory(
    client, isolated_db, temp_questions_dir, monkeypatch
) -> None:
    """Completed theory phase serves the coding interview page on reload."""
    del temp_questions_dir
    monkeypatch.setattr("random.shuffle", lambda items: None)

    interview = create_session(
        _theory_then_coding_session(),
        locale="en",
    )
    _complete_theory_section(interview.id)

    response = client.get(f"/interview/{interview.id}")
    assert response.status_code == 200
    assert 'id="coding-panel"' in response.text
    assert "coding-session" in response.text
