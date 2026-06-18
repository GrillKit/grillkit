# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for dashboard HTTP API (interview/api/dashboard.py)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.platform.services.config import AppConfig
from app.shared.infrastructure.models import Interview
from tests.helpers.interview_seed import persist_interview_with_answers
from tests.helpers.selection import minimal_selection_spec


def _config_with_locale(locale: str = "en") -> AppConfig:
    return AppConfig(
        provider_type="openai-compatible",
        base_url="http://localhost",
        model="gpt-4",
        locale=locale,
    )


class TestDashboardPage:
    """Tests for GET /."""

    def test_empty_state(self, client, isolated_db):
        """Dashboard shows welcome when no sessions exist."""
        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=_config_with_locale(),
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert "Start your first interview" in response.text or "interview" in response.text.lower()

    def test_shows_recent_sessions(self, client, isolated_db):
        """Dashboard lists up to 20 recent sessions."""
        # Seed 3 sessions
        for i in range(3):
            persist_interview_with_answers(
                Interview(
                    id=f"dash-{i}",
                    locale="en",
                    selection_spec=minimal_selection_spec(categories=["basics"]),
                    status="active",
                    started_at=datetime.now(UTC) - timedelta(minutes=i),
                ),
                [],
                question_count=5,
            )

        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=_config_with_locale(),
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert "dash-0" in response.text  # most recent
        assert "dash-1" in response.text
        assert "dash-2" in response.text

    def test_sort_order_desc(self, client, isolated_db):
        """Sessions are sorted by started_at DESC."""
        for i in range(3):
            persist_interview_with_answers(
                Interview(
                    id=f"dash-sort-{i}",
                    locale="en",
                    selection_spec=minimal_selection_spec(categories=["basics"]),
                    status="active",
                    started_at=datetime.now(UTC) - timedelta(hours=i),
                ),
                [],
                question_count=5,
            )

        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=_config_with_locale(),
        ):
            response = client.get("/")
        assert response.status_code == 200
        text = response.text
        # newest should appear before older
        assert text.index("dash-sort-0") < text.index("dash-sort-1")
        assert text.index("dash-sort-1") < text.index("dash-sort-2")

    def test_completed_session_links_to_results(self, client, isolated_db):
        """Completed sessions have 'View results' link pointing to /results."""
        from tests.helpers.completed_session_seed import seed_completed_theory_interview

        interview_id = seed_completed_theory_interview("dash-results-1")

        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=_config_with_locale(),
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert f"/interview/{interview_id}/results" in response.text

    def test_active_session_has_continue_link(self, client, isolated_db):
        """Active sessions have 'Continue' link pointing to /interview/{id}."""
        interview_id = "dash-continue-1"
        persist_interview_with_answers(
            Interview(
                id=interview_id,
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
                started_at=datetime.now(UTC),
            ),
            [],
            question_count=5,
        )

        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=_config_with_locale(),
        ):
            response = client.get("/")
        assert response.status_code == 200
        assert f"/interview/{interview_id}" in response.text

    def test_limit_20_sessions(self, client, isolated_db):
        """Dashboard caps at 20 sessions."""
        for i in range(25):
            persist_interview_with_answers(
                Interview(
                    id=f"dash-limit-{i:02d}",
                    locale="en",
                    selection_spec=minimal_selection_spec(categories=["basics"]),
                    status="active",
                    started_at=datetime.now(UTC) - timedelta(minutes=i),
                ),
                [],
                question_count=5,
            )

        with patch(
            "app.platform.services.config.ConfigService.get_config",
            return_value=_config_with_locale(),
        ):
            response = client.get("/")
        assert response.status_code == 200
        # The 21st (index 20) should NOT appear
        assert "dash-limit-20" not in response.text
        assert "dash-limit-00" in response.text
