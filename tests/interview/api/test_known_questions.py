# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for known questions HTTP API."""

import json

from app.interview.repositories.uow import InterviewUnitOfWork
from app.interview.services.known_questions import KnownQuestionsService


class TestKnownQuestionsApi:
    """Tests for /known-questions endpoints."""

    def test_list_empty(self, client, isolated_db) -> None:
        """GET returns empty lists when nothing is marked."""
        del isolated_db
        response = client.get("/known-questions")
        assert response.status_code == 200
        assert response.json() == {"theory": [], "coding": []}

    def test_mark_and_unmark(self, client, isolated_db) -> None:
        """POST and DELETE update the stored known lists."""
        del isolated_db
        mark = client.post(
            "/known-questions",
            json={"branch": "theory", "item_id": "bas-001"},
        )
        assert mark.status_code == 200
        assert mark.json()["theory"] == ["bas-001"]

        repeat = client.post(
            "/known-questions",
            json={"branch": "theory", "item_id": "bas-001"},
        )
        assert repeat.status_code == 200
        assert repeat.json()["theory"] == ["bas-001"]

        unmark = client.request(
            "DELETE",
            "/known-questions",
            content=json.dumps({"branch": "theory", "item_id": "bas-001"}),
            headers={"Content-Type": "application/json"},
        )
        assert unmark.status_code == 200
        assert unmark.json() == {"theory": [], "coding": []}

        missing = client.request(
            "DELETE",
            "/known-questions",
            content=json.dumps({"branch": "theory", "item_id": "bas-001"}),
            headers={"Content-Type": "application/json"},
        )
        assert missing.status_code == 200
        assert missing.json() == {"theory": [], "coding": []}

    def test_manage_page_renders(self, client, isolated_db) -> None:
        """Manage page returns HTML with marked IDs."""
        del isolated_db
        with InterviewUnitOfWork(auto_commit=True) as uow:
            KnownQuestionsService(uow).mark_known("coding", "bas-001")
        response = client.get("/known-questions/manage")
        assert response.status_code == 200
        assert "bas-001" in response.text
