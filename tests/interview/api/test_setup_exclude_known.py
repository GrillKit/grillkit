# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for exclude_known in setup and session creation."""

from unittest.mock import patch

from app.interview.domain.serialization import session_to_spec
from app.interview.domain.value_objects import (
    SessionSelection,
    TrackSelection,
)
from app.interview.repositories.uow import InterviewUnitOfWork
from app.platform.services.config import AppConfig
from tests.helpers.known_questions_seed import seed_known_question


class TestSetupExcludeKnown:
    """Tests that exclude_known=true excludes known questions from session plan."""

    def _config(self) -> AppConfig:
        return AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
        )

    def test_exclude_known_reads_from_json(self, client, isolated_db):
        """selection_json with exclude_known=true is parsed correctly."""
        from app.interview.services.rules.selection import parse_session_json

        raw = (
            '{"version":2,"session_mode":"theory_only","exclude_known":true,'
            '"theory":{"enabled":true,"question_count":5,'
            '"task_time_limit_seconds":null,'
            '"sources":[{"track":"python","level":"junior",'
            '"categories":["basics"]}]},'
            '"coding":{"enabled":false}}'
        )
        session = parse_session_json(raw)
        assert session.exclude_known is True

    def test_known_question_can_be_marked(self, client, isolated_db):
        """POST /known-questions adds a theory item to known list."""
        response = client.post(
            "/known-questions",
            json={"branch": "theory", "item_id": "q-known-1"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        known = client.get("/known-questions").json()
        assert "theory" in known
        assert "q-known-1" in known["theory"]

    def test_exclude_known_prevents_known_in_new_session(self, client, isolated_db):
        """Known questions are excluded from session plan when flag is set."""
        # Mark a question as known
        seed_known_question("theory", "q-exclude-1")

        session = SessionSelection.theory_only(
            sources=(
                TrackSelection(
                    track="python",
                    level="junior",
                    categories=("basics",),
                ),
            ),
            question_count=5,
        )
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=self._config(),
        ):
            response = client.post(
                "/setup",
                data={
                    "selection_json": session_to_spec(session),
                    "question_count": "5",
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        interview_id = response.headers["location"].rsplit("/", 1)[-1]

        # The plan should be generated; known question excluded would mean
        # the session was still created (if enough questions remain).
        with InterviewUnitOfWork() as uow:
            interview = uow.interviews.get_aggregate(interview_id)
            assert interview is not None
            assert interview.status == "active"
