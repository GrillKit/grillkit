# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for setup API cascaded options."""

from unittest.mock import MagicMock, patch

from app.platform.services.config import AppConfig


class TestSetupOptions:
    """Tests for GET /setup/options."""

    def test_lists_tracks(self, client):
        """Options without params returns available question-bank tracks."""
        with patch(
            "app.interview.api.setup.list_tracks",
            return_value=["database", "python"],
        ):
            response = client.get("/setup/options")
        assert response.status_code == 200
        assert response.json() == {"tracks": ["database", "python"]}

    def test_lists_levels_for_track(self, client):
        """Options with track returns levels for that track."""
        with (
            patch(
                "app.interview.api.setup.list_tracks",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior", "middle"],
            ),
        ):
            response = client.get("/setup/options", params={"track": "python"})
        assert response.status_code == 200
        assert response.json() == {"levels": ["junior", "middle"]}

    def test_lists_categories_for_track_and_level(self, client):
        """Options with track and level returns topic categories."""
        with (
            patch(
                "app.interview.api.setup.list_tracks",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior"],
            ),
            patch(
                "app.interview.api.setup.list_categories",
                return_value=["basics", "oop"],
            ),
        ):
            response = client.get(
                "/setup/options",
                params={"track": "python", "level": "junior"},
            )
        assert response.status_code == 200
        assert response.json() == {"categories": ["basics", "oop"]}

    def test_unknown_track_returns_404(self, client):
        """Unknown track slug returns 404."""
        with patch(
            "app.interview.api.setup.list_tracks",
            return_value=["python"],
        ):
            response = client.get("/setup/options", params={"track": "java"})
        assert response.status_code == 404


class TestSetupConfigRedirect:
    """Setup requires provider configuration before starting an interview."""

    def test_setup_get_redirects_without_config(self, client):
        """GET /setup redirects to /config when provider is not configured."""
        with patch(
            "app.platform.services.config.ConfigService.get_config", return_value=None
        ):
            response = client.get("/setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/config"

    def test_setup_post_redirects_without_config(self, client):
        """POST /setup redirects to /config when provider is not configured."""
        with patch(
            "app.platform.services.config.ConfigService.get_config", return_value=None
        ):
            response = client.post(
                "/setup",
                data={
                    "selection_json": (
                        '{"sources":[{"track":"python",'
                        '"level":"junior","categories":["basics"]}]}'
                    ),
                    "question_count": "5",
                },
                follow_redirects=False,
            )
        assert response.status_code == 303
        assert response.headers["location"] == "/config"

    def test_setup_get_shows_configured_locale(self, client):
        """GET /setup displays interview language from saved config."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="ru",
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch(
                "app.interview.api.setup.list_tracks",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior"],
            ),
            patch(
                "app.interview.api.setup.list_categories",
                return_value=["basics"],
            ),
        ):
            response = client.get("/setup")
        assert response.status_code == 200
        assert "Russian" in response.text
        assert 'name="locale"' not in response.text

    def test_setup_post_passes_timer_limit_when_enabled(self, client):
        """POST /setup forwards per-round timer seconds when the checkbox is set."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
        )
        captured: dict[str, object] = {}

        def fake_create(**kwargs: object) -> MagicMock:
            captured.update(kwargs)
            interview = MagicMock()
            interview.id = "timer-setup-id"
            return interview

        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch(
                "app.interview.services.creation.InterviewCreationService.create_interview",
                side_effect=fake_create,
            ),
        ):
            response = client.post(
                "/setup",
                data={
                    "selection_json": (
                        '{"sources":[{"track":"python",'
                        '"level":"junior","categories":["basics"]}]}'
                    ),
                    "question_count": "5",
                    "enable_question_timer": "on",
                    "question_time_minutes": "4",
                },
                follow_redirects=False,
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/interview/timer-setup-id"
        assert captured.get("question_time_limit_seconds") == 240
        assert "selection" in captured

    def test_setup_post_rejects_question_count_below_topics(self, client):
        """POST /setup rejects when question count is below selected topic count."""
        mock_config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            locale="en",
        )
        selection = (
            '{"sources":[{"track":"python","level":"junior",'
            '"categories":["basics","oop"]}]}'
        )
        with (
            patch(
                "app.platform.services.config.ConfigService.get_config",
                return_value=mock_config,
            ),
            patch(
                "app.interview.api.setup.list_tracks",
                return_value=["python"],
            ),
            patch(
                "app.interview.api.setup.list_levels",
                return_value=["junior"],
            ),
            patch(
                "app.interview.api.setup.list_categories",
                return_value=["basics", "oop"],
            ),
        ):
            response = client.post(
                "/setup",
                data={
                    "selection_json": selection,
                    "question_count": "1",
                },
            )

        assert response.status_code == 200
        assert "at least 2" in response.text
