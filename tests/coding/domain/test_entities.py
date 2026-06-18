# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for coding domain entities."""

from datetime import UTC, datetime, timedelta

import pytest

from app.coding.domain.entities import CodeRunAttempt, CodingSection, CodingTask
from app.coding.domain.exceptions import (
    CodingSectionNotActiveError,
    CodingTaskNotCurrentError,
    CodingTaskNotFoundError,
)
from app.coding.domain.value_objects import PlannedCodingTask
from app.interview.domain.value_objects import InterviewSelection, TrackSelection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_task(
    *,
    id: int = 1,
    task_id: str = "cod-001",
    order: int = 1,
    round_num: int = 0,
    submitted_code: str | None = None,
    score: int | None = None,
    feedback: str | None = None,
    started_at: datetime | None = None,
    task_spec: dict | None = None,
) -> CodingTask:
    now = datetime.now(UTC)
    return CodingTask(
        id=id,
        coding_section_id=1,
        interview_id="iv-001",
        task_id=task_id,
        order=order,
        round=round_num,
        prompt_text="Solve it.",
        task_spec=task_spec or {},
        submitted_code=submitted_code,
        submit_test_summary=None,
        score=score,
        feedback=feedback,
        started_at=started_at,
        created_at=now,
    )


def _make_section(
    *,
    status: str = "active",
    tasks: tuple[CodingTask, ...] = (),
    task_time_limit_seconds: int | None = None,
    section_score: int | None = None,
    section_feedback: dict[str, object] | None = None,
) -> CodingSection:
    return CodingSection(
        id=1,
        interview_id="iv-001",
        locale="en",
        selection=InterviewSelection(
            sources=(
                TrackSelection(track="python", level="junior", categories=("basics",)),
            )
        ),
        task_count=len(tasks),
        task_ids=tuple(t.task_id for t in tasks),
        task_time_limit_seconds=task_time_limit_seconds,
        status=status,  # type: ignore[arg-type]
        section_score=section_score,
        section_feedback=section_feedback,
        tasks=tasks,
    )


# ---------------------------------------------------------------------------
# CodingTask
# ---------------------------------------------------------------------------
class TestCodingTask:
    """Tests for the ``CodingTask`` entity."""

    def test_timer_deadline_raises_when_started_at_is_none(self) -> None:
        """timer_deadline raises ValueError when started_at is None."""
        task = _make_task()
        with pytest.raises(ValueError, match="has no started_at"):
            task.timer_deadline(limit_seconds=60)

    def test_timer_deadline_returns_deadline_when_started_at_set(self) -> None:
        """timer_deadline returns correct deadline when started_at is set."""
        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        task = _make_task(started_at=started_at)
        deadline = task.timer_deadline(limit_seconds=60)
        assert deadline == started_at + timedelta(seconds=60)

    def test_is_timer_expired_returns_false_when_limit_is_none(self) -> None:
        """is_timer_expired returns False when limit_seconds is None."""
        task = _make_task(started_at=datetime.now(UTC) - timedelta(hours=1))
        assert task.is_timer_expired(limit_seconds=None) is False

    def test_is_timer_expired_returns_false_when_started_at_is_none(self) -> None:
        """is_timer_expired returns False when started_at is None."""
        task = _make_task(started_at=None)
        assert task.is_timer_expired(limit_seconds=60) is False

    def test_is_timer_expired_returns_false_when_within_limit(self) -> None:
        """is_timer_expired returns False when time is within limit."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.is_timer_expired(
                limit_seconds=60, now=started_at + timedelta(seconds=30)
            )
            is False
        )

    def test_is_timer_expired_returns_true_when_past_limit(self) -> None:
        """is_timer_expired returns True when past the limit."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.is_timer_expired(
                limit_seconds=60, now=started_at + timedelta(seconds=70)
            )
            is True
        )

    def test_is_timer_expired_uses_grace_seconds(self) -> None:
        """is_timer_expired respects grace seconds before marking expired."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        # Exactly at limit, with default grace of 2s should still be False
        assert (
            task.is_timer_expired(
                limit_seconds=60, now=started_at + timedelta(seconds=60)
            )
            is False
        )
        # Past limit but within grace
        assert (
            task.is_timer_expired(
                limit_seconds=60, now=started_at + timedelta(seconds=61)
            )
            is False
        )
        # Past limit + grace
        assert (
            task.is_timer_expired(
                limit_seconds=60, now=started_at + timedelta(seconds=63)
            )
            is True
        )

    def test_is_timer_expired_with_zero_grace(self) -> None:
        """is_timer_expired with grace_seconds=0 expires exactly at limit."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.is_timer_expired(
                limit_seconds=60,
                now=started_at + timedelta(seconds=60),
                grace_seconds=0,
            )
            is True
        )
        assert (
            task.is_timer_expired(
                limit_seconds=60,
                now=started_at + timedelta(seconds=59),
                grace_seconds=0,
            )
            is False
        )

    def test_remaining_seconds_returns_none_when_limit_is_none(self) -> None:
        """remaining_seconds returns None when limit_seconds is None."""
        task = _make_task(started_at=datetime.now(UTC))
        assert task.remaining_seconds(limit_seconds=None) is None

    def test_remaining_seconds_returns_none_when_started_at_is_none(self) -> None:
        """remaining_seconds returns None when started_at is None."""
        task = _make_task(started_at=None)
        assert task.remaining_seconds(limit_seconds=60) is None

    def test_remaining_seconds_returns_correct_value(self) -> None:
        """remaining_seconds returns correct remaining time."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.remaining_seconds(
                limit_seconds=60, now=started_at + timedelta(seconds=20)
            )
            == 40
        )

    def test_remaining_seconds_is_non_negative(self) -> None:
        """remaining_seconds never returns negative values."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.remaining_seconds(
                limit_seconds=60, now=started_at + timedelta(seconds=90)
            )
            == 0
        )

    def test_client_timeout_due_returns_false_when_no_limit(self) -> None:
        """client_timeout_due returns False when limit_seconds is None."""
        task = _make_task(started_at=datetime.now(UTC))
        assert task.client_timeout_due(limit_seconds=None) is False

    def test_client_timeout_due_returns_false_when_not_started(self) -> None:
        """client_timeout_due returns False when started_at is None."""
        task = _make_task(started_at=None)
        assert task.client_timeout_due(limit_seconds=60) is False

    def test_client_timeout_due_returns_true_when_expired(self) -> None:
        """client_timeout_due returns True when timer is expired."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.client_timeout_due(
                limit_seconds=60, now=started_at + timedelta(seconds=65)
            )
            is True
        )

    def test_client_timeout_due_returns_true_when_zero_remaining(self) -> None:
        """client_timeout_due returns True when exactly zero seconds remain."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.client_timeout_due(
                limit_seconds=60, now=started_at + timedelta(seconds=60)
            )
            is True
        )

    def test_client_timeout_due_returns_false_when_time_remains(self) -> None:
        """client_timeout_due returns False when time still remains."""
        started_at = datetime.now(UTC)
        task = _make_task(started_at=started_at)
        assert (
            task.client_timeout_due(
                limit_seconds=60, now=started_at + timedelta(seconds=30)
            )
            is False
        )


# ---------------------------------------------------------------------------
# CodingSection
# ---------------------------------------------------------------------------
class TestCodingSection:
    """Tests for the ``CodingSection`` aggregate."""

    def test_start_raises_on_empty_planned_tasks(self) -> None:
        """start() raises ValueError when planned_tasks is empty."""
        with pytest.raises(ValueError, match="No coding tasks found"):
            CodingSection.start(
                interview_id="iv-001",
                selection=InterviewSelection(sources=()),
                locale="en",
                planned_tasks=(),
            )

    def test_start_creates_tasks_with_correct_order_and_round(self) -> None:
        """start() creates tasks with 1-based order and round=0."""
        planned = (
            PlannedCodingTask(
                id="cod-001", text="Task 1", task_spec={"language": "python"}
            ),
            PlannedCodingTask(
                id="cod-002", text="Task 2", task_spec={"language": "python"}
            ),
        )
        section = CodingSection.start(
            interview_id="iv-001",
            selection=InterviewSelection(sources=()),
            locale="en",
            planned_tasks=planned,
        )
        assert len(section.tasks) == 2
        assert section.tasks[0].order == 1
        assert section.tasks[0].round == 0
        assert section.tasks[0].task_id == "cod-001"
        assert section.tasks[1].order == 2
        assert section.tasks[1].round == 0
        assert section.tasks[1].task_id == "cod-002"

    def test_start_starts_timer_when_active_and_limit_set(self) -> None:
        """start() starts timer on first task when active and limit is set."""
        planned = (PlannedCodingTask(id="cod-001", text="Task 1", task_spec={}),)
        section = CodingSection.start(
            interview_id="iv-001",
            selection=InterviewSelection(sources=()),
            locale="en",
            planned_tasks=planned,
            task_time_limit_seconds=60,
            status="active",
        )
        assert section.tasks[0].started_at is not None

    def test_start_does_not_start_timer_when_pending(self) -> None:
        """start() does not start timer when status is pending."""
        planned = (PlannedCodingTask(id="cod-001", text="Task 1", task_spec={}),)
        section = CodingSection.start(
            interview_id="iv-001",
            selection=InterviewSelection(sources=()),
            locale="en",
            planned_tasks=planned,
            task_time_limit_seconds=60,
            status="pending",
        )
        assert section.tasks[0].started_at is None

    def test_start_does_not_start_timer_when_no_limit(self) -> None:
        """start() does not start timer when limit is None."""
        planned = (PlannedCodingTask(id="cod-001", text="Task 1", task_spec={}),)
        section = CodingSection.start(
            interview_id="iv-001",
            selection=InterviewSelection(sources=()),
            locale="en",
            planned_tasks=planned,
            task_time_limit_seconds=None,
            status="active",
        )
        assert section.tasks[0].started_at is None

    def test_with_activated_promotes_pending_to_active(self) -> None:
        """with_activated changes pending status to active."""
        section = _make_section(status="pending")
        activated = section.with_activated()
        assert activated.status == "active"

    def test_with_activated_returns_self_when_already_active(self) -> None:
        """with_activated returns self when status is already active."""
        section = _make_section(status="active")
        activated = section.with_activated()
        assert activated is section

    def test_with_activated_returns_self_when_completed(self) -> None:
        """with_activated returns self when status is completed."""
        section = _make_section(status="completed")
        activated = section.with_activated()
        assert activated is section

    def test_ensure_active_raises_when_not_active(self) -> None:
        """ensure_active raises CodingSectionNotActiveError when not active."""
        section = _make_section(status="completed")
        with pytest.raises(CodingSectionNotActiveError):
            section.ensure_active()

    def test_ensure_active_does_not_raise_when_active(self) -> None:
        """ensure_active does not raise when status is active."""
        section = _make_section(status="active")
        section.ensure_active()  # should not raise

    def test_find_first_unsubmitted_returns_first_pending(self) -> None:
        """find_first_unsubmitted returns the first task without submission."""
        tasks = (
            _make_task(submitted_code="code1"),
            _make_task(task_id="cod-002", submitted_code=None),
            _make_task(task_id="cod-003", submitted_code=None),
        )
        section = _make_section(tasks=tasks)
        first = section.find_first_unsubmitted()
        assert first is not None
        assert first.task_id == "cod-002"

    def test_find_first_unsubmitted_returns_none_when_all_submitted(self) -> None:
        """find_first_unsubmitted returns None when all tasks are submitted."""
        tasks = (
            _make_task(submitted_code="code1"),
            _make_task(task_id="cod-002", submitted_code="code2"),
        )
        section = _make_section(tasks=tasks)
        assert section.find_first_unsubmitted() is None

    def test_find_first_unsubmitted_returns_none_when_no_tasks(self) -> None:
        """find_first_unsubmitted returns None when there are no tasks."""
        section = _make_section(tasks=())
        assert section.find_first_unsubmitted() is None

    def test_is_complete_returns_false_when_tasks_unsubmitted(self) -> None:
        """is_complete returns False when tasks remain unsubmitted."""
        tasks = (_make_task(submitted_code=None),)
        section = _make_section(tasks=tasks)
        assert section.is_complete() is False

    def test_is_complete_returns_true_when_all_submitted(self) -> None:
        """is_complete returns True when all tasks are submitted."""
        tasks = (
            _make_task(submitted_code="code1"),
            _make_task(task_id="cod-002", submitted_code="code2"),
        )
        section = _make_section(tasks=tasks)
        assert section.is_complete() is True

    def test_is_complete_returns_false_when_no_tasks(self) -> None:
        """is_complete returns False when there are no tasks."""
        section = _make_section(tasks=())
        assert section.is_complete() is False

    def test_total_score_sums_submitted_scores(self) -> None:
        """total_score sums scores from all submitted tasks."""
        tasks = (
            _make_task(submitted_code="code1", score=3),
            _make_task(task_id="cod-002", submitted_code="code2", score=5),
            _make_task(task_id="cod-003", submitted_code=None, score=4),
        )
        section = _make_section(tasks=tasks)
        assert section.total_score() == 8

    def test_total_score_returns_zero_when_no_submissions(self) -> None:
        """total_score returns 0 when no tasks have been submitted."""
        tasks = (_make_task(submitted_code=None, score=3),)
        section = _make_section(tasks=tasks)
        assert section.total_score() == 0

    def test_max_score_for_submitted_rounds(self) -> None:
        """max_score computes max possible score for submitted rounds."""
        tasks = (
            _make_task(submitted_code="code1", score=3),
            _make_task(task_id="cod-002", submitted_code="code2", score=5),
            _make_task(task_id="cod-003", submitted_code=None, score=4),
        )
        section = _make_section(tasks=tasks)
        assert section.max_score() == CodingSection.MAX_SCORE_PER_ROUND * 2

    def test_max_score_returns_zero_when_no_submissions(self) -> None:
        """max_score returns 0 when no tasks have been submitted."""
        tasks = (_make_task(submitted_code=None),)
        section = _make_section(tasks=tasks)
        assert section.max_score() == 0

    def test_with_cached_section_feedback_sets_when_not_cached(self) -> None:
        """with_cached_section_feedback sets feedback when not already cached."""
        section = _make_section()
        updated = section.with_cached_section_feedback(
            feedback={"summary": "Good job"},
            section_score=4,
        )
        assert updated.section_feedback == {"summary": "Good job"}
        assert updated.section_score == 4

    def test_with_cached_section_feedback_skips_when_already_cached(self) -> None:
        """with_cached_section_feedback returns self when feedback already cached."""
        section = _make_section(
            section_feedback={"summary": "Already cached"}, section_score=3
        )
        updated = section.with_cached_section_feedback(
            feedback={"summary": "New feedback"},
            section_score=5,
        )
        assert updated is section
        assert updated.section_feedback == {"summary": "Already cached"}

    def test_start_timer_for_task_sets_started_at(self) -> None:
        """start_timer_for_task sets started_at when limit is configured."""
        tasks = (_make_task(id=1),)
        section = _make_section(tasks=tasks, task_time_limit_seconds=60)
        when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        updated = section.start_timer_for_task(task_row_id=1, when=when)
        assert updated.tasks[0].started_at == when

    def test_start_timer_for_task_does_nothing_when_no_limit(self) -> None:
        """start_timer_for_task returns self when no time limit is set."""
        tasks = (_make_task(id=1),)
        section = _make_section(tasks=tasks, task_time_limit_seconds=None)
        updated = section.start_timer_for_task(task_row_id=1)
        assert updated is section

    def test_start_timer_for_task_does_not_overwrite_existing_started_at(self) -> None:
        """start_timer_for_task does not overwrite an existing started_at."""
        existing = datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC)
        tasks = (_make_task(id=1, started_at=existing),)
        section = _make_section(tasks=tasks, task_time_limit_seconds=60)
        when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        updated = section.start_timer_for_task(task_row_id=1, when=when)
        assert updated.tasks[0].started_at == existing

    def test_start_timer_for_task_ignores_non_matching_task(self) -> None:
        """start_timer_for_task ignores tasks that don't match the row id."""
        tasks = (_make_task(id=1), _make_task(id=2, task_id="cod-002"))
        section = _make_section(tasks=tasks, task_time_limit_seconds=60)
        when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        updated = section.start_timer_for_task(task_row_id=1, when=when)
        assert updated.tasks[0].started_at == when
        assert updated.tasks[1].started_at is None

    def test_with_submit_test_summary_updates_correct_task(self) -> None:
        """with_submit_test_summary sets fields on the matching task only."""
        tasks = (
            _make_task(id=1, submitted_code=None),
            _make_task(id=2, task_id="cod-002", submitted_code=None),
        )
        section = _make_section(tasks=tasks)
        updated = section.with_submit_test_summary(
            task_row_id=2,
            summary={"status": "success"},
            source_code="def solve(): pass",
        )
        assert updated.tasks[0].submitted_code is None
        assert updated.tasks[1].submitted_code == "def solve(): pass"
        assert updated.tasks[1].submit_test_summary == {"status": "success"}

    def test_with_timed_out_round_marks_task_correctly(self) -> None:
        """with_timed_out_round marks the task with TIME_EXPIRED_SOURCE_CODE."""
        tasks = (_make_task(id=1),)
        section = _make_section(tasks=tasks)
        updated = section.with_timed_out_round(task_row_id=1, feedback="Time ran out")
        assert updated.tasks[0].submitted_code == CodingTask.TIME_EXPIRED_SOURCE_CODE
        assert updated.tasks[0].submit_test_summary == {"status": "timeout"}
        assert updated.tasks[0].score == 0
        assert updated.tasks[0].feedback == "Time ran out"

    def test_with_timed_out_round_ignores_non_matching_task(self) -> None:
        """with_timed_out_round ignores tasks that don't match the row id."""
        tasks = (
            _make_task(id=1),
            _make_task(id=2, task_id="cod-002"),
        )
        section = _make_section(tasks=tasks)
        updated = section.with_timed_out_round(task_row_id=2, feedback="Time ran out")
        assert updated.tasks[0].submitted_code is None
        assert updated.tasks[1].submitted_code == CodingTask.TIME_EXPIRED_SOURCE_CODE

    def test_with_evaluation_updates_correct_task(self) -> None:
        """with_evaluation updates score and feedback on the matching task."""
        tasks = (
            _make_task(id=1, task_id="cod-001"),
            _make_task(id=2, task_id="cod-002"),
        )
        section = _make_section(tasks=tasks)
        updated = section.with_evaluation(
            task_id="cod-002",
            round_num=0,
            score=4,
            feedback="Great work",
        )
        assert updated.tasks[0].score is None
        assert updated.tasks[1].score == 4
        assert updated.tasks[1].feedback == "Great work"

    def test_with_evaluation_finds_correct_round(self) -> None:
        """with_evaluation finds the correct task round."""
        tasks = (
            _make_task(id=1, task_id="cod-001", round_num=0),
            _make_task(id=2, task_id="cod-001", round_num=1),
        )
        section = _make_section(tasks=tasks)
        updated = section.with_evaluation(
            task_id="cod-001",
            round_num=1,
            score=3,
            feedback="Round 1 feedback",
        )
        assert updated.tasks[0].score is None
        assert updated.tasks[1].score == 3
        assert updated.tasks[1].feedback == "Round 1 feedback"

    def test_max_round_for_task_returns_highest_round(self) -> None:
        """max_round_for_task returns the highest round for a task."""
        tasks = (
            _make_task(id=1, task_id="cod-001", round_num=0),
            _make_task(id=2, task_id="cod-001", round_num=1),
            _make_task(id=3, task_id="cod-001", round_num=2),
        )
        section = _make_section(tasks=tasks)
        assert section.max_round_for_task("cod-001") == 2

    def test_max_round_for_task_returns_zero_when_no_match(self) -> None:
        """max_round_for_task returns 0 when task does not exist."""
        tasks = (_make_task(task_id="cod-001"),)
        section = _make_section(tasks=tasks)
        assert section.max_round_for_task("cod-999") == 0

    def test_with_follow_up_creates_new_round(self) -> None:
        """with_follow_up creates a new follow-up task round."""
        tasks = (
            _make_task(
                id=1,
                task_id="cod-001",
                order=1,
                round_num=0,
                task_spec={"language": "python"},
            ),
        )
        section = _make_section(tasks=tasks)
        updated, follow_up = section.with_follow_up(
            task_id="cod-001",
            prompt_text="Follow-up prompt",
            starter_code="# starter",
        )
        assert len(updated.tasks) == 2
        assert follow_up.round == 1
        assert follow_up.task_id == "cod-001"
        assert follow_up.order == 1
        assert follow_up.prompt_text == "Follow-up prompt"
        assert follow_up.task_spec["starter_code"] == "# starter"
        assert follow_up.submitted_code is None
        assert follow_up.score is None

    def test_with_follow_up_without_starter_code(self) -> None:
        """with_follow_up works without starter_code."""
        tasks = (
            _make_task(
                id=1,
                task_id="cod-001",
                order=1,
                round_num=0,
                task_spec={"language": "python"},
            ),
        )
        section = _make_section(tasks=tasks)
        updated, follow_up = section.with_follow_up(
            task_id="cod-001",
            prompt_text="Follow-up prompt",
            starter_code=None,
        )
        assert "starter_code" not in follow_up.task_spec
        assert follow_up.round == 1

    def test_find_next_unsubmitted_after_returns_next_pending(self) -> None:
        """find_next_unsubmitted_after returns the next pending task."""
        tasks = (
            _make_task(id=1, submitted_code="code1"),
            _make_task(id=2, task_id="cod-002", submitted_code=None),
            _make_task(id=3, task_id="cod-003", submitted_code=None),
        )
        section = _make_section(tasks=tasks)
        next_task = section.find_next_unsubmitted_after(current_index=0)
        assert next_task is not None
        assert next_task.task_id == "cod-002"

    def test_find_next_unsubmitted_after_returns_none_when_no_more(self) -> None:
        """find_next_unsubmitted_after returns None when no pending tasks remain."""
        tasks = (
            _make_task(id=1, submitted_code="code1"),
            _make_task(id=2, task_id="cod-002", submitted_code="code2"),
        )
        section = _make_section(tasks=tasks)
        assert section.find_next_unsubmitted_after(current_index=0) is None

    def test_require_current_task_returns_matching_task(self) -> None:
        """require_current_task returns the task when it is current."""
        tasks = (
            _make_task(id=1, task_id="cod-001", submitted_code=None),
            _make_task(id=2, task_id="cod-002", submitted_code=None),
        )
        section = _make_section(tasks=tasks)
        current = section.require_current_task("cod-001")
        assert current.task_id == "cod-001"

    def test_require_current_task_raises_when_not_current(self) -> None:
        """require_current_task raises when task is not the current one."""
        tasks = (
            _make_task(id=1, task_id="cod-001", submitted_code=None),
            _make_task(id=2, task_id="cod-002", submitted_code=None),
        )
        section = _make_section(tasks=tasks)
        with pytest.raises(CodingTaskNotCurrentError):
            section.require_current_task("cod-002")

    def test_require_current_task_raises_when_all_submitted(self) -> None:
        """require_current_task raises when all tasks are submitted."""
        tasks = (_make_task(id=1, task_id="cod-001", submitted_code="code1"),)
        section = _make_section(tasks=tasks)
        with pytest.raises(CodingTaskNotCurrentError):
            section.require_current_task("cod-001")

    def test_find_task_returns_matching_task(self) -> None:
        """find_task returns the task matching task_id and round."""
        tasks = (
            _make_task(id=1, task_id="cod-001", round_num=0),
            _make_task(id=2, task_id="cod-001", round_num=1),
        )
        section = _make_section(tasks=tasks)
        found = section.find_task("cod-001", round_num=1)
        assert found.id == 2

    def test_find_task_raises_when_not_found(self) -> None:
        """find_task raises CodingTaskNotFoundError when task is not found."""
        tasks = (_make_task(task_id="cod-001"),)
        section = _make_section(tasks=tasks)
        with pytest.raises(CodingTaskNotFoundError):
            section.find_task("cod-999", round_num=0)


# ---------------------------------------------------------------------------
# CodeRunAttempt
# ---------------------------------------------------------------------------
class TestCodeRunAttempt:
    """Tests for the ``CodeRunAttempt`` entity."""

    def test_code_run_attempt_creation(self) -> None:
        """CodeRunAttempt can be constructed with all fields."""
        now = datetime.now(UTC)
        attempt = CodeRunAttempt(
            id=1,
            coding_task_id=2,
            attempt_no=1,
            source_code="def solve(): pass",
            language="python",
            status="success",  # type: ignore[arg-type]
            stdout="3\n",
            stderr=None,
            compile_output=None,
            tests_passed=1,
            tests_total=1,
            test_results=(),
            duration_ms=120,
            created_at=now,
        )
        assert attempt.id == 1
        assert attempt.coding_task_id == 2
        assert attempt.attempt_no == 1
        assert attempt.source_code == "def solve(): pass"
        assert attempt.language == "python"
        assert attempt.status == "success"
        assert attempt.stdout == "3\n"
        assert attempt.duration_ms == 120
        assert attempt.created_at == now
