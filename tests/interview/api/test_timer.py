# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Timer expired tests for theory and coding sessions."""

from datetime import UTC, datetime, timedelta

from app.interview.domain.serialization import selection_to_spec
from app.interview.domain.value_objects import SectionBranchSpec, SessionSelection, TrackSelection
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from app.theory.domain.entities import TheoryTask
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec
from tests.helpers.coding_seed import seed_active_coding_interview


class TestTheoryTimer:
    """Theory timer expiry (S14)."""

    def test_timer_expired_scores_zero_and_advances(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """Timer expired → score=0, auto next question."""
        started = datetime.now(UTC) - timedelta(seconds=120)
        interview_id = persist_interview_with_answers(
            Interview(
                id="timer-theory-1",
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
            ),
            [
                Answer(
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q1?",
                    started_at=started,
                ),
                Answer(
                    question_id="q2",
                    order=2,
                    round=0,
                    question_text="Q2?",
                ),
            ],
            question_count=2,
            task_time_limit_seconds=60,
        )

        override_ws_ai_provider(client, [])

        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            ws.send_json({"type": "timeout", "question_id": "q1", "round": 0})
            feedback = ws.receive_json()

        assert feedback["type"] == "feedback"
        assert feedback["timed_out"] is True
        assert feedback["next_question"]["question_id"] == "q2"

        reloaded = InterviewQuery.load(interview_id)
        assert reloaded is not None
        q1 = next(a for a in reloaded.answers if a.question_id == "q1")
        assert q1.answer_text == TheoryTask.TIME_EXPIRED_ANSWER_TEXT
        assert q1.score == 0

    def test_no_timer_does_not_timeout(self, client, isolated_db, override_ws_ai_provider):
        """Without timer enabled, timeout msg is rejected."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="timer-theory-2",
                locale="en",
                selection_spec=minimal_selection_spec(),
                status="active",
            ),
            [
                Answer(question_id="q1", order=1, round=0, question_text="Q?"),
            ],
            question_count=1,
            task_time_limit_seconds=None,
        )

        override_ws_ai_provider(client, [])

        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            ws.send_json({"type": "timeout", "question_id": "q1", "round": 0})
            err = ws.receive_json()

        assert err["type"] == "error"


class TestCodingTimer:
    """Coding timer expiry (S14)."""

    def test_timer_expired_scores_zero_and_advances(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """Timer expired coding task → score=0, next task."""
        from app.shared.infrastructure.models import CodingSection, CodingTask
        coding_selection_spec = selection_to_spec(
            SessionSelection(
                session_mode="coding_only",
                theory=SectionBranchSpec(enabled=False, question_count=0, task_time_limit_seconds=None, sources=()),
                coding=SectionBranchSpec(
                    enabled=True,
                    question_count=2,
                    task_time_limit_seconds=60,
                    sources=(TrackSelection(track="python", level="junior", categories=("basics",)),),
                ),
            ).coding_selection
        )
        with InterviewUnitOfWork(auto_commit=True) as uow:
            from app.shared.infrastructure.models import Interview as InterviewModel
            db_interview = InterviewModel(
                id="timer-coding-1",
                locale="en",
                selection_spec=minimal_selection_spec(),
                status="active",
                session_mode="coding_only",
            )
            uow.session.add(db_interview)
            uow.flush()
            section = uow.session.query(CodingSection).filter_by(interview_id="timer-coding-1").first()
            if not section:
                section = CodingSection(
                    interview_id="timer-coding-1",
                    selection_spec=coding_selection_spec,
                    task_count=2,
                    task_time_limit_seconds=60,
                    locale="en",
                    status="active",
                )
                uow.session.add(section)
                uow.flush()
            for i in range(2):
                uow.session.add(CodingTask(
                    coding_section_id=section.id,
                    task_id=f"cod-t{i}",
                    order=i + 1,
                    round=0,
                    prompt_text=f"Task {i}",
                    task_spec='{"language":"python"}',
                ))
            uow.session.flush()
            # Set started_at on first task
            tasks = uow.session.query(CodingTask).filter_by(coding_section_id=section.id).order_by(CodingTask.order).all()
            tasks[0].started_at = datetime.now(UTC) - timedelta(seconds=120)
            tasks[1].started_at = None

        override_ws_ai_provider(client, [])

        with client.websocket_connect("/interview/timer-coding-1/coding/ws") as ws:
            ws.send_json({"type": "timeout", "task_id": "cod-t0", "round": 0})
            feedback = ws.receive_json()

        assert feedback["type"] == "feedback"
        assert feedback["task_id"] == "cod-t0"
        # Next task should be set
        assert feedback["next_task"] is not None

        with InterviewUnitOfWork() as uow:
            task = uow.session.query(CodingTask).filter_by(task_id="cod-t0").one()
            assert task.submitted_code == "[Time expired]"
            assert task.score == 0
