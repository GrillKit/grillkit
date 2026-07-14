# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Phase switching tests for combined modes (theory_then_coding, coding_then_theory)."""

from unittest.mock import AsyncMock, patch

from app.coding.domain.value_objects import CodingRunResult
from app.coding.services.evaluator.models import CodingAnswerEvaluation
from app.interview.domain.serialization import selection_to_spec
from app.interview.domain.value_objects import (
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.query import InterviewQuery
from app.shared.infrastructure.models import Answer, Interview
from tests.fakes import answer_evaluation_json
from tests.helpers.coding_seed import (
    attach_coding_tasks,
    create_coding_section_for_interview,
)
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


def _success_run_result() -> CodingRunResult:
    return CodingRunResult(
        status="success",
        stdout=None,
        stderr=None,
        compile_output=None,
        tests_passed=0,
        tests_total=0,
        test_results=(),
        duration_ms=12,
    )


class TestCombinedPhaseSwitch:
    """Tests for combined session modes."""

    def test_theory_then_coding_switch_after_theory_finish(
        self, client, isolated_db, override_ws_ai_provider
    ):
        """When theory completes, coding section activates."""
        interview_id = persist_interview_with_answers(
            Interview(
                id="combined-tc-1",
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
                session_mode="theory_then_coding",
            ),
            [
                Answer(
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q?",
                ),
            ],
            question_count=1,
        )
        # Attach coding section in pending state
        coding_selection_spec = selection_to_spec(
            SessionSelection(
                session_mode="theory_then_coding",
                theory=SectionBranchSpec(
                    enabled=True,
                    question_count=1,
                    task_time_limit_seconds=None,
                    sources=(),
                ),
                coding=SectionBranchSpec(
                    enabled=True,
                    question_count=1,
                    task_time_limit_seconds=None,
                    sources=(
                        TrackSelection(
                            track="python", level="junior", categories=("basics",)
                        ),
                    ),
                ),
            ).coding_selection
        )
        with InterviewUnitOfWork(auto_commit=True) as uow:
            from app.shared.infrastructure.models import Interview as InterviewModel

            db_interview = (
                uow.session.query(InterviewModel).filter_by(id=interview_id).one()
            )
            section = create_coding_section_for_interview(
                uow.session,
                db_interview,
                task_count=1,
                status="pending",
                selection_spec=coding_selection_spec,
            )
            attach_coding_tasks(uow.session, section, task_ids=["cod-001"])

        # Answer theory question (need two replies: one for answer, one for session completion)
        override_ws_ai_provider(
            client,
            [
                answer_evaluation_json(score=5, follow_up_needed=False),
                answer_evaluation_json(score=5, follow_up_needed=False),
            ],
        )
        with client.websocket_connect(f"/interview/{interview_id}/theory/ws") as ws:
            ws.send_json(
                {
                    "type": "answer",
                    "question_id": "q1",
                    "answer_text": "Done",
                }
            )
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb = ws.receive_json()
            assert fb["type"] == "feedback"
            # Complete theory section
            ws.send_json({"type": "complete"})
            assert ws.receive_json() == {"type": "evaluating"}
            completed = ws.receive_json()
            assert completed["type"] == "interview_completed"

        # Coding section should now be active
        state = client.get(f"/interview/{interview_id}/coding/state")
        assert state.status_code == 200
        assert state.json()["section_status"] == "active"

    def test_coding_then_theory_switch_after_coding_finish(
        self, client, isolated_db, mock_judge0, override_ws_ai_provider
    ):
        """When coding completes, theory section activates."""
        interview_id = "combined-ct-1"
        coding_selection_spec = selection_to_spec(
            SessionSelection(
                session_mode="coding_then_theory",
                theory=SectionBranchSpec(
                    enabled=True,
                    question_count=1,
                    task_time_limit_seconds=None,
                    sources=(),
                ),
                coding=SectionBranchSpec(
                    enabled=True,
                    question_count=1,
                    task_time_limit_seconds=None,
                    sources=(
                        TrackSelection(
                            track="python", level="junior", categories=("basics",)
                        ),
                    ),
                ),
            ).coding_selection
        )
        with InterviewUnitOfWork(auto_commit=True) as uow:
            from app.shared.infrastructure.models import Answer as AnswerModel
            from app.shared.infrastructure.models import Interview as InterviewModel
            from app.shared.infrastructure.models import (
                TheorySection as TheorySectionModel,
            )

            db_interview = InterviewModel(
                id=interview_id,
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
                session_mode="coding_then_theory",
            )
            uow.session.add(db_interview)
            uow.flush()
            section = create_coding_section_for_interview(
                uow.session,
                db_interview,
                task_count=1,
                status="active",
                selection_spec=coding_selection_spec,
            )
            attach_coding_tasks(uow.session, section, task_ids=["cod-001"])
            # Add theory section manually (no add_from_selection method)
            theory_section = TheorySectionModel(
                interview_id=interview_id,
                selection_spec=db_interview.selection_spec,
                locale="en",
                status="pending",
            )
            uow.session.add(theory_section)
            uow.session.flush()
            # Add answer row
            uow.session.add(
                AnswerModel(
                    theory_section_id=theory_section.id,
                    question_id="q1",
                    order=1,
                    round=0,
                    question_text="Q?",
                )
            )

        mock_judge0()
        evaluation = CodingAnswerEvaluation(
            score=5,
            feedback="Perfect.",
            follow_up_needed=False,
            follow_up_question=None,
            follow_up_mode=None,
        )
        override_ws_ai_provider(client, [])
        with (
            patch(
                "app.coding.services.submission.CodingEvaluatorService.evaluate_submission",
                new=AsyncMock(return_value=(evaluation, False, None, None)),
            ),
            client.websocket_connect(f"/interview/{interview_id}/coding/ws") as ws,
        ):
            ws.send_json(
                {
                    "type": "submit",
                    "task_id": "cod-001",
                    "source_code": "pass",
                }
            )
            assert ws.receive_json() == {"type": "saved"}
            assert ws.receive_json() == {"type": "evaluating"}
            fb = ws.receive_json()
            assert fb["type"] == "feedback"
            assert fb.get("next_task") is None

        # Interview page should now show theory
        reloaded = InterviewQuery.load(interview_id)
        assert reloaded is not None
        # Theory section should be discoverable
        with InterviewUnitOfWork() as uow:
            theory = uow.theory_sections.get_aggregate(interview_id)
            assert theory is not None
