# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheoryQueryService."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock

from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.sections import SectionEvaluationSummary
from app.theory.domain.entities import TheorySection, TheoryTask
from app.theory.services.query import TheoryQueryService


def _task(
    task_id: int,
    question_id: str,
    order: int,
    answer_text: str | None = None,
    score: int | None = None,
    feedback: str | None = None,
    round_num: int = 0,
) -> TheoryTask:
    """Build a minimal theory task."""
    return TheoryTask(
        id=task_id,
        theory_section_id=1,
        interview_id="iv-1",
        question_id=question_id,
        order=order,
        round=round_num,
        question_text=f"Q{order}?",
        question_code=None,
        answer_text=answer_text,
        score=score,
        feedback=feedback,
        started_at=None,
        created_at=datetime.now(UTC),
        expected_points=(),
    )


def _section(
    *,
    tasks: list[TheoryTask] | None = None,
    section_feedback: dict[str, object] | None = None,
) -> TheorySection:
    """Build a theory section with the given tasks."""
    return TheorySection(
        id=1,
        interview_id="iv-1",
        locale="en",
        selection=InterviewSelection(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            )
        ),
        question_count=2,
        question_ids=("q1", "q2"),
        task_time_limit_seconds=None,
        status="active",
        section_score=None,
        section_feedback=section_feedback,
        tasks=tuple(tasks) if tasks else (),
    )


def test_get_evaluation_summary_returns_correct_summary() -> None:
    """get_evaluation_summary returns score, items, and cached narrative."""
    t1 = _task(1, "q1", 1, answer_text="A1", score=4, feedback="Good")
    t2 = _task(2, "q2", 2, answer_text="A2", score=5, feedback="Great")
    section = _section(tasks=[t1, t2])

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryQueryService(mock_uow)
    result = service.get_evaluation_summary("iv-1")

    assert isinstance(result, SectionEvaluationSummary)
    assert result.section == "theory"
    assert result.score == 9
    assert result.max_score == 10
    assert result.skipped is False
    assert len(result.items) == 2
    assert result.items[0]["question_id"] == "q1"
    assert result.items[0]["score"] == 4
    assert result.items[0]["feedback"] == "Good"
    assert result.cached_narrative is None


def test_get_evaluation_summary_uses_cached_narrative() -> None:
    """Cached section_feedback is forwarded in the summary when present."""
    t1 = _task(1, "q1", 1, answer_text="A1", score=4)
    cached = {"summary": "Already evaluated"}
    section = _section(tasks=[t1], section_feedback=cached)

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryQueryService(mock_uow)
    result = service.get_evaluation_summary("iv-1")

    assert result.cached_narrative == cached


def test_get_evaluation_summary_returns_none_when_missing() -> None:
    """get_evaluation_summary returns None when no theory section exists."""
    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = None

    service = TheoryQueryService(mock_uow)
    result = service.get_evaluation_summary("missing")

    assert result is None


def test_get_evaluation_summary_skipped_section() -> None:
    """Skipped sections report zero scores."""
    t1 = _task(1, "q1", 1, answer_text="A1", score=4)
    section = replace(_section(tasks=[t1]), status="skipped")

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryQueryService(mock_uow)
    result = service.get_evaluation_summary("iv-1")

    assert result.score == 0
    assert result.max_score == 0
    assert result.skipped is True


def test_sources_text_for_section_returns_text() -> None:
    """sources_text_for_section returns selection summary for prompts."""
    section = _section()

    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = section

    service = TheoryQueryService(mock_uow)
    result = service.sources_text_for_section("iv-1")

    assert "Python" in result
    assert "junior" in result
    assert "basics" in result


def test_sources_text_for_section_returns_empty_when_missing() -> None:
    """sources_text_for_section returns empty string when no section exists."""
    mock_uow = MagicMock(spec=InterviewUnitOfWork)
    mock_uow.theory_sections.get_aggregate.return_value = None

    service = TheoryQueryService(mock_uow)
    result = service.sources_text_for_section("missing")

    assert result == ""


def test_qa_items_from_section_builds_correct_items() -> None:
    """_qa_items_from_section includes only answered tasks."""
    t1 = _task(1, "q1", 1, answer_text="A1", score=3, feedback="OK", round_num=0)
    t2 = _task(2, "q1", 1, answer_text=None, score=None, feedback=None, round_num=1)
    t3 = _task(3, "q2", 2, answer_text="A2", score=5, feedback="Nice", round_num=0)
    section = _section(tasks=[t1, t2, t3])

    items = TheoryQueryService._qa_items_from_section(section)

    assert len(items) == 2
    assert items[0]["question_id"] == "q1"
    assert items[0]["answer_text"] == "A1"
    assert items[0]["score"] == 3
    assert items[0]["round"] == 0
    assert items[0]["feedback"] == "OK"
    assert items[1]["question_id"] == "q2"
    assert items[1]["score"] == 5


def test_qa_items_ignores_unanswered_tasks() -> None:
    """Tasks without answer_text are omitted from Q&A items."""
    t1 = _task(1, "q1", 1, answer_text=None, score=None)
    section = _section(tasks=[t1])

    items = TheoryQueryService._qa_items_from_section(section)

    assert items == ()
