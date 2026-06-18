# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for creating interviews in all 4 session modes."""

from unittest.mock import patch

from app.interview.domain.serialization import session_to_spec
from app.interview.domain.value_objects import (
    SectionBranchSpec,
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.platform.services.config import AppConfig


class TestSetupModes:
    """End-to-end creation of interviews in each session mode."""

    def _config(self) -> AppConfig:
        return AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
        )

    def _post_setup(self, client, selection_json: str, **extra):
        data = {
            "selection_json": selection_json,
            "question_count": "5",
            "coding_question_count": "2",
        }
        data.update(extra)
        return client.post("/setup", data=data, follow_redirects=False)

    def test_theory_only(self, client, isolated_db):
        """Mode theory_only creates interview with theory section only."""
        session = SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
            question_count=3,
            task_time_limit_seconds=180,
        )
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=self._config(),
        ):
            response = self._post_setup(
                client,
                session_to_spec(session),
                question_count="3",
                enable_question_timer="on",
                question_time_minutes="3",
            )

        assert response.status_code == 303
        location = response.headers["location"]
        assert "/interview/" in location
        interview_id = location.rsplit("/", 1)[-1]

        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview is not None
            assert interview.session_mode == "theory_only"
            section = uow.theory_sections.get_aggregate(interview_id)
            assert section is not None
            assert section.question_count == 3
            assert section.task_time_limit_seconds == 180

    def test_coding_only(self, client, isolated_db):
        """Mode coding_only creates interview with coding section only."""
        session = SessionSelection(
            session_mode="coding_only",
            theory=SectionBranchSpec(
                enabled=False,
                question_count=0,
                task_time_limit_seconds=None,
                sources=(),
            ),
            coding=SectionBranchSpec(
                enabled=True,
                question_count=2,
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
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=self._config(),
            ),
            patch(
                "app.interview.services.rules.selection.is_coding_available",
                return_value=True,
            ),
        ):
            response = self._post_setup(
                client,
                session_to_spec(session),
                coding_question_count="2",
                enable_coding_timer="on",
                coding_time_minutes="10",
            )

        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview is not None
            assert interview.session_mode == "coding_only"
            section = uow.coding_sections.get_aggregate(interview_id)
            assert section is not None
            assert section.task_count == 2
            assert section.task_time_limit_seconds == 600

    def test_theory_then_coding(self, client, isolated_db):
        """Mode theory_then_coding creates both sections."""
        session = SessionSelection(
            session_mode="theory_then_coding",
            theory=SectionBranchSpec(
                enabled=True,
                question_count=3,
                task_time_limit_seconds=180,
                sources=(
                    TrackSelection(
                        track="database",
                        level="middle",
                        categories=("sql-advanced",),
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
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=self._config(),
            ),
            patch(
                "app.interview.services.rules.selection.is_coding_available",
                return_value=True,
            ),
        ):
            response = self._post_setup(
                client,
                session_to_spec(session),
                question_count="3",
                coding_question_count="1",
                enable_question_timer="on",
                question_time_minutes="3",
                enable_coding_timer="on",
                coding_time_minutes="10",
            )

        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview.session_mode == "theory_then_coding"
            theory = uow.theory_sections.get_aggregate(interview_id)
            coding = uow.coding_sections.get_aggregate(interview_id)
            assert theory is not None
            assert coding is not None
            assert theory.question_count == 3

    def test_coding_then_theory(self, client, isolated_db):
        """Mode coding_then_theory creates both sections."""
        session = SessionSelection(
            session_mode="coding_then_theory",
            theory=SectionBranchSpec(
                enabled=True,
                question_count=2,
                task_time_limit_seconds=120,
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("basics",),
                    ),
                ),
            ),
            coding=SectionBranchSpec(
                enabled=True,
                question_count=2,
                task_time_limit_seconds=480,
                sources=(
                    TrackSelection(
                        track="python",
                        level="junior",
                        categories=("basics",),
                    ),
                ),
            ),
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=self._config(),
            ),
            patch(
                "app.interview.services.rules.selection.is_coding_available",
                return_value=True,
            ),
        ):
            response = self._post_setup(
                client,
                session_to_spec(session),
                question_count="2",
                coding_question_count="2",
                enable_question_timer="on",
                question_time_minutes="2",
                enable_coding_timer="on",
                coding_time_minutes="8",
            )

        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview.session_mode == "coding_then_theory"
            theory = uow.theory_sections.get_aggregate(interview_id)
            coding = uow.coding_sections.get_aggregate(interview_id)
            assert theory is not None
            assert coding is not None
